import io
import shutil
import tempfile
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from .models import Material, Favorite, Attachment
from .validators import inspect_file


@override_settings(DEMO_MODE=True)
class AcceptanceTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media = tempfile.mkdtemp(prefix='shag-tests-')
        cls.override = override_settings(MEDIA_ROOT=cls.media)
        cls.override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.override.disable()
        shutil.rmtree(cls.media)

    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo', stdout=io.StringIO())
        cls.user = get_user_model().objects.create_user(email='parent@example.test', password='Safe-test-password-382!', first_name='Анна')
        cls.staff = get_user_model().objects.create_superuser(email='editor@example.test', password='Safe-test-password-382!', first_name='Редактор')
        cls.item = Material.objects.get(slug='reading-1')

    def test_a01_catalog_pagination_and_demo_disclosure(self):
        response = self.client.get(reverse('catalog'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].paginator.count, 18)
        self.assertEqual(len(response.context['page_obj']), 12)
        self.assertContains(response, 'Задания ожидают проверки педагогом')

    def test_a02_cyrillic_case_insensitive_search(self):
        response = self.client.get(reverse('catalog'), {'q': self.item.title.upper()})
        self.assertEqual(list(response.context['page_obj']), [self.item])
        self.assertEqual(self.client.get(reverse('catalog'), {'q': 'СЛОГИ'}).context['page_obj'].paginator.count, 3)

    def test_a03_filters_are_anded(self):
        response = self.client.get(reverse('catalog'), {'direction': 'reading', 'age': '5-7', 'duration': '5', 'level': 'initial', 'format': 'worksheet'})
        self.assertEqual(list(response.context['page_obj']), [self.item])

    def test_a04_empty_results_and_reset(self):
        response = self.client.get(reverse('catalog'), {'direction': 'reading', 'age': '7-10', 'duration': '5'})
        self.assertContains(response, 'Заданий по этим условиям пока нет')
        self.assertContains(response, 'Сбросить фильтры')
        self.assertEqual(self.client.get(reverse('catalog')).context['page_obj'].paginator.count, 18)

    def test_a05_detail_and_safe_return(self):
        response = self.client.get(self.item.get_absolute_url(), {'back': '/materials/?direction=reading&age=5-7'})
        for text in ['Инструкция взрослому', 'Если пока трудно', 'Если хочется больше', 'Задание', self.item.goal]:
            self.assertContains(response, text)
        self.assertEqual(response.context['back'], '/materials/?direction=reading&age=5-7')
        response = self.client.get(self.item.get_absolute_url(), {'back': 'https://example.com/'})
        self.assertEqual(response.context['back'], '/materials/')

    def test_a06_pdf_view_and_download(self):
        file = self.item.attachments.get()
        for suffix, disposition in [('', 'inline'), ('?download=1', 'attachment')]:
            response = self.client.get(reverse('attachment', args=[file.pk]) + suffix)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'application/pdf')
            self.assertIn(disposition, response['Content-Disposition'])
            self.assertTrue(b''.join(response.streaming_content).startswith(b'%PDF-'))
            self.assertEqual(response['Cache-Control'], 'private, no-store')
            self.assertEqual(response['X-Frame-Options'], 'SAMEORIGIN')

    def test_a07_a08_favorites_persist_and_are_private(self):
        url = reverse('toggle_favorite', args=[self.item.slug])
        self.client.force_login(self.user)
        self.assertRedirects(self.client.post(url), self.item.get_absolute_url())
        other_device = Client()
        self.assertTrue(other_device.login(email=self.user.email, password='Safe-test-password-382!'))
        self.assertContains(other_device.get(reverse('favorites')), self.item.title)
        other_device.force_login(self.staff)
        self.assertNotContains(other_device.get(reverse('favorites')), self.item.title)
        self.client.post(url)
        self.assertFalse(Favorite.objects.filter(user=self.user, material=self.item).exists())

    def test_a09_regular_user_cannot_edit(self):
        self.client.force_login(self.user)
        url = reverse('admin:library_material_change', args=[self.item.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.assertEqual(self.client.post(url, {'title': 'Changed'}).status_code, 302)
        self.item.refresh_from_db()
        self.assertNotEqual(self.item.title, 'Changed')

    def test_a10_publication_lifecycle_hides_detail_and_files(self):
        item = Material.objects.get(pk=self.item.pk)
        item.status = 'draft'
        item.save()
        file_url = reverse('attachment', args=[item.attachments.get().pk])
        self.assertEqual(self.client.get(item.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(file_url).status_code, 404)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(item.get_absolute_url()).status_code, 200)
        self.client.logout()
        item.status = 'published'
        with self.assertRaises(ValidationError):
            item.save()
        # This reviewer string is isolated test-fixture data, never seed content.
        item.reviewed = True
        item.reviewer = 'TEST FIXTURE ONLY'
        item.save()
        with override_settings(DEMO_MODE=False):
            self.assertEqual(self.client.get(item.get_absolute_url()).status_code, 200)
        Favorite.objects.create(user=self.user, material=item)
        item.status = 'draft'
        item.save()
        self.client.force_login(self.user)
        self.assertNotContains(self.client.get(reverse('favorites')), item.title)
        self.assertEqual(self.client.get(file_url).status_code, 404)
        self.assertTrue(Favorite.objects.filter(user=self.user, material=item).exists())

    def test_a11_invalid_and_oversize_files(self):
        for name, content in [('bad.exe', b'MZ'), ('fake.pdf', b'not a PDF'), ('empty.pdf', b''),
                              ('huge.pdf', b'%PDF-' + b'x' * (20 * 1024 * 1024))]:
            with self.subTest(name=name), self.assertRaises(ValidationError):
                inspect_file(SimpleUploadedFile(name, content))

    def test_a11_image_and_pptx_signature_checks(self):
        from PIL import Image
        from zipfile import ZipFile
        png = io.BytesIO()
        Image.new('RGB', (10, 10), 'white').save(png, format='PNG')
        self.assertEqual(inspect_file(SimpleUploadedFile('ok.png', png.getvalue()))[0], 'image/png')
        with self.assertRaises(ValidationError):
            inspect_file(SimpleUploadedFile('wrong.jpg', png.getvalue()))
        for valid in [False, True]:
            ppt = io.BytesIO()
            with ZipFile(ppt, 'w') as archive:
                archive.writestr('[Content_Types].xml', '<Types/>')
                if valid:
                    archive.writestr('ppt/presentation.xml', '<presentation/>')
            if valid:
                self.assertIn('presentationml', inspect_file(SimpleUploadedFile('file.pptx', ppt.getvalue()))[0])
            else:
                with self.assertRaises(ValidationError):
                    inspect_file(SimpleUploadedFile('file.pptx', ppt.getvalue()))

    def test_a11_max_three_attachments(self):
        for index in range(2):
            Attachment.objects.create(material=self.item, name=f'Extra {index}', file=SimpleUploadedFile(f'{index}.pdf', b'%PDF-1.4\n%%EOF'))
        with self.assertRaises(ValidationError):
            Attachment.objects.create(material=self.item, name='Fourth', file=SimpleUploadedFile('4.pdf', b'%PDF-1.4\n%%EOF'))

    def test_a13_url_restores_filter_sort_and_page(self):
        response = self.client.get(reverse('catalog'), {'sort': 'duration', 'page': '2'})
        self.assertEqual(response.context['page_obj'].number, 2)
        self.assertEqual(response.context['form']['sort'].value(), 'duration')
        response = self.client.get(reverse('catalog'), {'direction': 'math', 'age': '7-10', 'duration': '15'})
        self.assertEqual(response.context['form']['direction'].value(), 'math')
        self.assertEqual(response.context['page_obj'].paginator.count, 2)
        self.assertEqual(self.client.get(reverse('catalog'), {'page': 'nonsense'}).status_code, 200)

    def test_a14_demo_is_complete_honest_and_idempotent(self):
        self.assertEqual(Material.objects.count(), 18)
        self.assertEqual(Attachment.objects.filter(content_type='application/pdf').count(), 18)
        self.assertEqual(Material.objects.filter(reviewed=True).count(), 0)
        for item in Material.objects.all():
            for field in ['title', 'goal', 'instructions', 'task', 'easier', 'harder', 'source', 'permission']:
                self.assertTrue(getattr(item, field))
        call_command('seed_demo', stdout=io.StringIO())
        self.assertEqual(Material.objects.count(), 18)
        self.assertEqual(Attachment.objects.count(), 18)
        with override_settings(DEMO_MODE=False):
            self.assertEqual(self.client.get(reverse('catalog')).context['page_obj'].paginator.count, 0)

    def test_csrf_and_post_only_mutations(self):
        secure_client = Client(enforce_csrf_checks=True)
        secure_client.force_login(self.user)
        url = reverse('toggle_favorite', args=[self.item.slug])
        self.assertEqual(secure_client.post(url).status_code, 403)
        self.assertEqual(secure_client.get(url).status_code, 405)
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)

    def test_signup_login_case_insensitive_and_return(self):
        response = self.client.post(reverse('signup') + '?next=/materials/reading-1/', {
            'first_name': 'Мария', 'email': 'NEW@EXAMPLE.TEST',
            'password1': 'Some-secure-pass-9304!', 'password2': 'Some-secure-pass-9304!'})
        self.assertRedirects(response, self.item.get_absolute_url())
        self.assertTrue(get_user_model().objects.filter(email='new@example.test').exists())
        self.client.post(reverse('logout'))
        response = self.client.post(reverse('signup'), {'first_name': 'Мария', 'email': 'New@example.test',
            'password1': 'Some-secure-pass-9304!', 'password2': 'Some-secure-pass-9304!'})
        self.assertContains(response, 'Этот email уже зарегистрирован.')
        response = self.client.post(reverse('login'), {'username': 'NEW@EXAMPLE.TEST', 'password': 'Some-secure-pass-9304!'})
        self.assertEqual(response.status_code, 302)

    def test_open_redirect_blocked_and_guest_prompt(self):
        response = self.client.get(reverse('favorites'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
        self.client.force_login(self.user)
        response = self.client.post(reverse('toggle_favorite', args=[self.item.slug]), {'next': 'https://attacker.example/'})
        self.assertEqual(response.url, self.item.get_absolute_url())

    def test_staff_can_use_admin_forms(self):
        self.client.force_login(self.staff)
        for name in ['admin:library_user_add', 'admin:library_material_add']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:library_material_change', args=[self.item.pk])).status_code, 200)

    def test_blank_published_material_rejected(self):
        item = Material.objects.get(pk=self.item.pk)
        item.task = '  '
        item.status = 'published'
        item.reviewed = True
        item.reviewer = 'TEST FIXTURE ONLY'
        item.attachments.all().delete()
        with self.assertRaises(ValidationError):
            item.save()
