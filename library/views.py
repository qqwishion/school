from urllib.parse import urlencode
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction, connection
from django.db.models import Q
from django.db.models.functions import Collate, Lower
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.decorators.clickjacking import xframe_options_sameorigin
from .forms import FilterForm, SignupForm, EmailAuthenticationForm
from .models import Material, Favorite, Attachment


def safe_next(request, fallback):
    target = request.POST.get('next') or request.GET.get('next') or fallback
    return target if url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()) else fallback


class SignInView(LoginView):
    template_name = 'registration/login.html'
    authentication_form = EmailAuthenticationForm


def signup(request):
    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()
        except IntegrityError:
            form.add_error('email', 'Этот email уже зарегистрирован.')
        else:
            login(request, user)
            return redirect(safe_next(request, reverse('catalog')))
    return render(request, 'registration/signup.html', {'form': form, 'next': safe_next(request, reverse('catalog'))})


def catalog(request, only_favorites=False):
    materials = Material.objects.visible().select_related('direction')
    if only_favorites:
        materials = materials.filter(favorite__user=request.user)
    form = FilterForm(request.GET)
    form.is_valid()
    data = form.cleaned_data
    query = data.get('q', '').strip()
    if query:
        if connection.vendor == 'postgresql':
            # Explicit Unicode collation keeps Cyrillic case conversion correct
            # even when PostgreSQL/test databases were initialized with locale C.
            materials = materials.alias(
                search_title=Lower(Collate('title', 'und-x-icu')),
                search_goal=Lower(Collate('goal', 'und-x-icu')),
                search_keywords=Lower(Collate('keywords', 'und-x-icu')),
            ).filter(Q(search_title__contains=query.lower()) | Q(search_goal__contains=query.lower()) |
                     Q(search_keywords__contains=query.lower()))
        else:
            # SQLite LIKE is ASCII-only; keep Cyrillic searches correct in the local pilot.
            matching = [m.pk for m in materials.select_related(None).only('pk', 'title', 'goal', 'keywords')
                        if query.casefold() in ' '.join([m.title, m.goal, m.keywords]).casefold()]
            materials = materials.filter(pk__in=matching)
    for field in ['direction', 'age', 'level', 'format']:
        if data.get(field):
            materials = materials.filter(**{field: data[field]})
    if data.get('duration'):
        materials = materials.filter(duration__lte=data['duration'])
    ordering = {'title': ['title', 'pk'], 'duration': ['duration', 'title', 'pk']}
    materials = materials.order_by(*ordering.get(data.get('sort'), ['direction__order', 'title', 'pk']))
    page = Paginator(materials, 12).get_page(request.GET.get('page'))
    saved_ids = set(Favorite.objects.filter(user=request.user).values_list('material_id', flat=True)) if request.user.is_authenticated else set()
    params = request.GET.copy()
    params.pop('page', None)
    tabs = []
    choices = [('', 'Все материалы', '✳')] + [
        (direction.slug, direction.name, {'reading': 'Аа', 'writing': '✎', 'math': '123',
         'attention': '◎', 'memory': '◇', 'speech': '“”'}.get(direction.slug, '•'))
        for direction in form.fields['direction'].queryset]
    for slug, name, icon in choices:
        tab_params = params.copy()
        tab_params.pop('direction', None)
        if slug:
            tab_params['direction'] = slug
        tabs.append({'name': name, 'icon': icon, 'active': request.GET.get('direction', '') == slug,
                     'url': request.path + ('?' + tab_params.urlencode() if tab_params else '')})
    return render(request, 'catalog.html', {'form': form, 'page_obj': page, 'saved_ids': saved_ids,
                  'only_favorites': only_favorites, 'query_string': params.urlencode(),
                  'catalog_return': request.get_full_path(), 'direction_tabs': tabs})


@login_required
def favorites(request):
    return catalog(request, only_favorites=True)


def accessible(request):
    return Material.objects.all() if request.user.is_staff else Material.objects.visible()


def detail(request, slug):
    material = get_object_or_404(accessible(request).select_related('direction'), slug=slug)
    saved = request.user.is_authenticated and Favorite.objects.filter(user=request.user, material=material).exists()
    back = request.GET.get('back', reverse('catalog'))
    if not url_has_allowed_host_and_scheme(back, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        back = reverse('catalog')
    attachments = list(material.attachments.all())
    pdf = next((a for a in attachments if a.content_type == 'application/pdf'), None)
    return render(request, 'detail.html', {'material': material, 'saved': saved, 'attachments': attachments, 'pdf': pdf, 'back': back})


@require_POST
@login_required
def toggle_favorite(request, slug):
    material = get_object_or_404(Material.objects.visible(), slug=slug)
    # Lock the owner to serialize concurrent toggles on PostgreSQL.
    from .models import User
    with transaction.atomic():
        User.objects.select_for_update().get(pk=request.user.pk)
        entry, created = Favorite.objects.get_or_create(user=request.user, material=material)
        if not created:
            entry.delete()
    return redirect(safe_next(request, material.get_absolute_url()))


@xframe_options_sameorigin
def attachment(request, pk):
    item = get_object_or_404(Attachment.objects.select_related('material'), pk=pk, material__in=accessible(request))
    try:
        response = FileResponse(item.file.open('rb'), as_attachment=request.GET.get('download') == '1',
                                filename=item.name, content_type=item.content_type)
    except (FileNotFoundError, OSError):
        raise Http404('Файл временно недоступен')
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def cover(request, pk):
    material = get_object_or_404(accessible(request), pk=pk)
    if not material.cover:
        raise Http404
    try:
        response = FileResponse(material.cover.open('rb'))
    except OSError:
        raise Http404
    response['Cache-Control'] = 'private, no-store'
    return response
