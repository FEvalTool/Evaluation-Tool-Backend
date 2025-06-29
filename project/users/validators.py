from django.core.validators import RegexValidator

class UserValidators:
    phone_validator = RegexValidator(
        regex=r"^(03[2-9]|05[6|8|9]|07[0-9]|08[1-9]|09[0-9])\d{7}$",
        message="Phone number must be entered in the Vietnamese phone number format.",
    )
    identity_number_validator = RegexValidator(
        regex=r"^(00[1-9]|0[1-9][0-9]|09[0-6])[0-9]{9}$",
        message="Identity number must be entered in the Vietnamese identity nuber format.",
    )
    