from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class CadastroForm(UserCreationForm):
    email = forms.EmailField(label="E-mail", required=True)
    time_nome = forms.CharField(label="Nome do seu time", max_length=40, required=False)

    class Meta:
        model = User
        fields = ("username", "email")
        labels = {"username": "Nome de usuário"}

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Já existe uma conta com este e-mail.")
        return email

    def save(self, commit=True):
        usuario = super().save(commit)
        perfil = usuario.perfil
        perfil.time_nome = self.cleaned_data.get("time_nome") or usuario.username
        perfil.save(update_fields=["time_nome"])
        return usuario
