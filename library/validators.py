from pathlib import Path
from zipfile import ZipFile, BadZipFile
from django.core.exceptions import ValidationError
from PIL import Image


def inspect_file(file):
    ext = Path(file.name).suffix.lower()
    types = {'.pdf': 'application/pdf', '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
             '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}
    if ext not in types:
        raise ValidationError('Разрешены только PDF, PPTX, PNG и JPEG.')
    if file.size > 20 * 1024 * 1024:
        raise ValidationError('Файл больше 20 МБ.')
    if file.size == 0:
        raise ValidationError('Файл пуст.')
    try:
        file.open('rb')
        file.seek(0)
        if ext == '.pdf':
            if not file.read(8).startswith(b'%PDF-'):
                raise ValidationError('Содержимое не соответствует PDF.')
        elif ext == '.pptx':
            with ZipFile(file) as archive:
                names = archive.namelist()
                if '[Content_Types].xml' not in names or 'ppt/presentation.xml' not in names or any('vbaProject' in n for n in names):
                    raise ValidationError('Некорректная презентация PPTX или содержит макросы.')
        else:
            pic = Image.open(file)
            if pic.format != ('PNG' if ext == '.png' else 'JPEG'):
                raise ValidationError('Содержимое не соответствует расширению изображения.')
            pic.verify()
    except (OSError, ValueError, BadZipFile) as exc:
        raise ValidationError('Файл повреждён или имеет неверный формат.') from exc
    finally:
        file.seek(0)
    return types[ext], file.size
