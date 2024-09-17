from django import forms
from django_countries.fields import CountryField
from django_countries.widgets import CountrySelectWidget
from django.contrib.auth.forms import AuthenticationForm
# from django.contrib.auth.models import User
from allauth.account.forms import LoginForm

PAYMENT_CHOICES = (
    ('S', 'Stripe'),
    ('P', 'PayPal'),
)

class LoginForm(forms.Form):
    pass
    
class CheckoutForm(forms.Form):
    street_address = forms.CharField(
        label='Street Address',
        widget=forms.TextInput(attrs={
            'placeholder': '1234 Main St',
            'class': 'form-control'
        })
    )
    apartment_address = forms.CharField(
        label='Apartment Address',
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Apartment or suite',
            'class': 'form-control'
        })
    )
    country = CountryField(
        blank_label='(select country)'
    ).formfield(
        widget=CountrySelectWidget(attrs={
            'class': 'custom-select d-block w-100'
        })
    )
    zip = forms.CharField(
        label='ZIP Code',
        widget=forms.TextInput(attrs={
            'class': 'form-control'
        })
    )
    same_shipping_address = forms.BooleanField(
        label='Same shipping address',
        required=False
    )
    save_info = forms.BooleanField(
        label='Save this information for next time',
        required=False
    )
    payment_option = forms.ChoiceField(
        label='Payment Option',
        widget=forms.RadioSelect,
        choices=PAYMENT_CHOICES
    )

class CouponForm(forms.Form):
    code = forms.CharField(
        label='Promo Code',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your promo code'
        })
    )

class RefundForm(forms.Form):
    ref_code = forms.CharField(
        label='Reference Code',
        max_length=20
    )
    message = forms.CharField(
        label='Message',
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'Tell us why you are requesting a refund'
        })
    )
    email = forms.EmailField(
        label='Email Address'
    )


