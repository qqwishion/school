from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, Direction, Material


class SignupForm(UserCreationForm):
    first_name = forms.CharField(label='Имя', max_length=150)
    email = forms.EmailField(label='Email')

    class Meta:
        model = User
        fields = ['first_name', 'email', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Этот email уже зарегистрирован.')
        return email


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label='Email', widget=forms.EmailInput(attrs={'autofocus': True, 'autocomplete': 'email'}))

    def clean_username(self):
        return self.cleaned_data['username'].strip().lower()


class FilterForm(forms.Form):
    q = forms.CharField(label='Поиск по библиотеке', required=False, max_length=150,
                       widget=forms.TextInput(attrs={'placeholder': 'Например, слоги или счёт', 'type': 'search'}))
    direction = forms.ModelChoiceField(label='Направление', queryset=Direction.objects.all(), to_field_name='slug',
                                      required=False, empty_label='Все направления')
    age = forms.ChoiceField(label='Возраст', required=False, choices=[('', 'Любой возраст')] + Material.AGE_CHOICES)
    level = forms.ChoiceField(label='Сложность', required=False, choices=[('', 'Любая сложность')] + Material.LEVEL_CHOICES)
    format = forms.ChoiceField(label='Формат', required=False, choices=[('', 'Все форматы')] + Material.FORMAT_CHOICES)
    duration = forms.TypedChoiceField(label='Длительность', required=False, coerce=int, empty_value=None,
                                     choices=[('', 'Любая длительность'), ('5', 'До 5 минут'), ('10', 'До 10 минут'), ('15', 'До 15 минут')])
    sort = forms.ChoiceField(label='Порядок', required=False, choices=[('', 'По направлению'), ('title', 'По названию'), ('duration', 'Сначала короткие')])
