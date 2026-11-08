from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable


def make_pdf(material):
    font_paths = [Path(settings.BASE_DIR) / 'assets' / 'DejaVuSans.ttf',
                  Path('C:/Windows/Fonts/arial.ttf'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
    font = next((p for p in font_paths if p.exists()), None)
    if not font:
        raise RuntimeError('Install DejaVu Sans or set up assets/DejaVuSans.ttf for Cyrillic PDF.')
    if 'Shag' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('Shag', str(font)))
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='ShagBody', fontName='Shag', fontSize=12, leading=19, spaceAfter=10))
    styles.add(ParagraphStyle(name='ShagTitle', fontName='Shag', fontSize=23, leading=31, spaceAfter=16, textColor=colors.HexColor('#203e36')))
    styles.add(ParagraphStyle(name='ShagSmall', fontName='Shag', fontSize=9, leading=13, spaceAfter=10))
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=45, leftMargin=45, topMargin=40, bottomMargin=40,
                            title=material.title, author='Шаг — демонстрационная библиотека')
    story = []
    def add(text, style='ShagBody'):
        story.append(Paragraph(escape(text).replace('\n', '<br/>'), styles[style]))
    add('ШАГ / ' + str(material.direction), 'ShagSmall')
    add(material.title, 'ShagTitle')
    add(f'{material.get_age_display()} · {material.get_level_display()} · {material.duration} минут', 'ShagSmall')
    add('Демонстрационный пример. Ожидает содержательной проверки педагогом.', 'ShagSmall')
    add('Цель: ' + material.goal)
    add('Приготовьте: ' + material.supplies)
    add('Взрослому: ' + material.instructions)
    story.append(HRFlowable(width='100%', color=colors.HexColor('#ccd7c6')))
    story.append(Spacer(1, 14))
    add(material.task)
    story.append(Spacer(1, 24))
    add('Если пока трудно: ' + material.easier, 'ShagSmall')
    add('Если хочется больше: ' + material.harder, 'ShagSmall')
    add(material.source + '\n' + material.permission, 'ShagSmall')
    doc.build(story)
    return output.getvalue()
