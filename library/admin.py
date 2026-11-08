from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, AdminUserCreationForm
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from .models import User, Direction, Material, Attachment, Favorite


class AdultCreationForm(AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ['email', 'first_name']


class AdultChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'


@admin.register(User)
class AdultAdmin(UserAdmin):
    add_form = AdultCreationForm
    form = AdultChangeForm
    ordering = ['email']
    list_display = ['email', 'first_name', 'is_staff', 'is_active']
    search_fields = ['email', 'first_name']
    fieldsets = ((None, {'fields': ('email', 'password')}), ('Профиль взрослого', {'fields': ('first_name',)}),
                 ('Доступ', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
                 ('Даты', {'fields': ('last_login', 'date_joined')}))
    add_fieldsets = ((None, {'classes': ('wide',), 'fields': ('email', 'first_name', 'password1', 'password2')}),)


class AttachmentSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        active = [f for f in self.forms if f.cleaned_data and not f.cleaned_data.get('DELETE') and f.cleaned_data.get('file')]
        if len(active) > 3:
            raise ValidationError('Не более трёх вложений на материал.')
        if self.instance.status == 'published' and not self.instance.task.strip() and not active:
            raise ValidationError('У опубликованного материала должен остаться текст задания или вложение.')


class AttachmentInline(admin.TabularInline):
    model = Attachment
    formset = AttachmentSet
    extra = 1
    max_num = 3
    readonly_fields = ['size', 'content_type']


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ['title', 'direction', 'age', 'status', 'reviewed']
    list_filter = ['status', 'direction', 'reviewed', 'age']
    search_fields = ['title', 'goal', 'keywords']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [AttachmentInline]
    readonly_fields = ['created_at', 'updated_at']
    actions = ['publish', 'unpublish']

    @admin.action(description='Опубликовать после проверки')
    def publish(self, request, queryset):
        for item in queryset:
            item.status = 'published'
            try:
                item.save()
            except ValidationError as exc:
                self.message_user(request, f'{item}: {"; ".join(exc.messages)}', level='error')

    @admin.action(description='Снять с публикации')
    def unpublish(self, request, queryset):
        queryset.update(status='draft')


@admin.register(Direction)
class DirectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'order']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ['user', 'material', 'created_at']
