import uuid
from pathlib import Path
from django.conf import settings
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.urls import reverse


class EmailUserManager(UserManager):
    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('Email обязателен')
        user = self.model(email=email.strip().lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.update(is_staff=True, is_superuser=True)
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField('Email', unique=True)
    first_name = models.CharField('Имя', max_length=150)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name']
    objects = EmailUserManager()

    class Meta:
        constraints = [models.UniqueConstraint(Lower('email'), name='unique_email_case_insensitive')]

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)


class Direction(models.Model):
    name = models.CharField('Название', max_length=80, unique=True)
    slug = models.SlugField(unique=True)
    order = models.PositiveSmallIntegerField('Порядок', default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'направление'
        verbose_name_plural = 'направления'

    def __str__(self):
        return self.name


def private_path(instance, filename):
    return f'attachments/{uuid.uuid4().hex}{Path(filename).suffix.lower()}'


def cover_path(instance, filename):
    return f'covers/{uuid.uuid4().hex}{Path(filename).suffix.lower()}'


class MaterialQuerySet(models.QuerySet):
    def visible(self):
        statuses = ['published'] + (['demo'] if settings.DEMO_MODE else [])
        return self.filter(status__in=statuses)


class Material(models.Model):
    AGE_CHOICES = [('5-7', '5–7 лет'), ('7-10', '7–10 лет')]
    LEVEL_CHOICES = [('initial', 'Начальный'), ('basic', 'Базовый')]
    FORMAT_CHOICES = [('worksheet', 'Рабочий лист'), ('activity', 'Карточка занятия')]
    STATUS_CHOICES = [('draft', 'Черновик'), ('published', 'Опубликован'), ('demo', 'Демонстрационный пример')]
    slug = models.SlugField('Адрес', unique=True)
    title = models.CharField('Название', max_length=150)
    goal = models.CharField('Цель', max_length=300)
    direction = models.ForeignKey(Direction, on_delete=models.PROTECT, verbose_name='Направление')
    age = models.CharField('Возраст', max_length=10, choices=AGE_CHOICES)
    level = models.CharField('Сложность', max_length=10, choices=LEVEL_CHOICES)
    format = models.CharField('Формат', max_length=15, choices=FORMAT_CHOICES)
    duration = models.PositiveSmallIntegerField('Минуты', validators=[MinValueValidator(1), MaxValueValidator(15)])
    instructions = models.TextField('Инструкция взрослому')
    task = models.TextField('Задание', blank=True)
    supplies = models.TextField('Принадлежности')
    easier = models.TextField('Как упростить')
    harder = models.TextField('Как усложнить')
    keywords = models.CharField('Ключевые слова', max_length=400, blank=True)
    cover = models.ImageField('Обложка', upload_to=cover_path, blank=True)
    source = models.TextField('Источник')
    permission = models.TextField('Разрешение на использование')
    reviewed = models.BooleanField('Проверено педагогом', default=False)
    reviewer = models.CharField('Кто и когда проверил (заполняется педагогом)', max_length=250, blank=True)
    status = models.CharField('Статус', max_length=12, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = MaterialQuerySet.as_manager()

    class Meta:
        ordering = ['direction__order', 'title']
        verbose_name = 'материал'
        verbose_name_plural = 'материалы'
        permissions = [('publish_material', 'Может публиковать материалы')]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('detail', args=[self.slug])

    def clean(self):
        super().clean()
        if self.status == 'published':
            errors = {}
            for field in ['title', 'goal', 'instructions', 'supplies', 'easier', 'harder', 'source', 'permission']:
                if not str(getattr(self, field, '')).strip():
                    errors[field] = 'Обязательно для публикации.'
            if not self.reviewed or not self.reviewer.strip():
                errors['reviewed'] = 'Нужна содержательная проверка педагогом и запись о проверяющем.'
            if not self.task.strip() and not (self.pk and self.attachments.exists()):
                errors['task'] = 'Добавьте текст задания или сначала сохраните черновик с вложением.'
            if errors:
                raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class Attachment(models.Model):
    material = models.ForeignKey(Material, related_name='attachments', on_delete=models.CASCADE)
    file = models.FileField('Файл', upload_to=private_path)
    name = models.CharField('Название', max_length=200)
    size = models.PositiveIntegerField('Размер', editable=False, default=0)
    content_type = models.CharField('Тип', max_length=100, editable=False)

    class Meta:
        verbose_name = 'вложение'
        verbose_name_plural = 'вложения'

    def clean(self):
        from .validators import inspect_file
        super().clean()
        if self.file:
            self.content_type, self.size = inspect_file(self.file)
        if self.material_id and Attachment.objects.filter(material_id=self.material_id).exclude(pk=self.pk).count() >= 3:
            raise ValidationError('Не более трёх вложений на материал.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'material'], name='unique_user_material')]
        verbose_name = 'избранное'
        verbose_name_plural = 'избранное'
