from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from library.demo_data import DIRECTIONS, ACTIVITIES
from library.models import Direction, Material, Attachment
from library.pdf import make_pdf


class Command(BaseCommand):
    help = 'Create 18 original, explicitly unreviewed demo activities and 18 printable PDFs. Idempotent; never overwrites edits.'

    @transaction.atomic
    def handle(self, *args, **options):
        count = 0
        for order, (slug, name) in enumerate(DIRECTIONS):
            direction, _ = Direction.objects.get_or_create(slug=slug, defaults={'name': name, 'order': order})
            for index, (title, goal, task, easier, harder) in enumerate(ACTIVITIES[slug]):
                material, created = Material.objects.get_or_create(slug=f'{slug}-{index + 1}', defaults={
                    'title': title, 'goal': goal, 'direction': direction, 'age': '5-7' if index == 0 else '7-10',
                    'level': 'initial' if index == 0 else 'basic', 'format': 'worksheet' if index != 1 else 'activity',
                    'duration': [5, 10, 15][index],
                    'instructions': '1. Прочитайте задание заранее и подготовьте принадлежности.\n'
                                    '2. Объясните цель простыми словами, покажите первый пример.\n'
                                    '3. Предлагайте по одному шагу. Не торопите; при усталости сделайте паузу.\n'
                                    '4. В конце обсудите, что получилось, без сравнения с другими детьми.',
                    'task': task, 'supplies': 'Бумага, карандаш; для заданий с предметами — крупные безопасные фишки и указанные в задании предметы под наблюдением взрослого.',
                    'easier': easier, 'harder': harder, 'keywords': f'{name} {title} {"слоги слова" if slug == "reading" else "развитие занятие"}',
                    'source': 'Авторский демонстрационный текст, подготовленный для проекта «Шаг» с помощью ИИ.',
                    'permission': 'Текст создан для этого проекта; допускаются печать и адаптация в учебных занятиях. Сторонние материалы не использованы.',
                    'status': 'demo', 'reviewed': False,
                })
                if created:
                    count += 1
                if created and not material.attachments.exists():
                    attachment = Attachment(material=material, name=f'{material.slug}.pdf')
                    attachment.file = ContentFile(make_pdf(material), name=f'{material.slug}.pdf')
                    attachment.save()
        self.stdout.write(self.style.SUCCESS(f'Created {count} demo materials. Pedagogical review remains pending.'))
