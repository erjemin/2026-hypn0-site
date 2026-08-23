from django import forms


class HalftoneGenerateForm(forms.Form):
    """
    Форма валидации входных параметров для генерации гипнотического SVG.
    """
    SHAPE_CHOICES = [
        ("circle", "Круг"),
        ("ring", "Кольцо"),
        ("triangle", "Треугольник"),
        ("square", "Квадрат"),
        ("diamond", "Ромб"),
        ("hexagon", "Шестиугольник"),
        ("star", "Звезда"),
        ("cross", "Крестик"),
        ("line", "Линия"),
        ("wave", "Волна"),
        ("heart", "Сердечко"),
    ]

    image = forms.ImageField(
        required=True,
        error_messages={
            "required": "Покорми Гипножабу изображением!",
            "invalid_image": "Гипножаба не может переварить этот файл. Нужна картинка (PNG, JPG, WEBP).",
        },
    )
    shape = forms.ChoiceField(
        choices=SHAPE_CHOICES,
        initial="circle",
        required=False,
    )
    cols = forms.IntegerField(
        min_value=20,
        max_value=200,
        initial=80,
        required=False,
    )
    max_radius = forms.IntegerField(
        min_value=3,
        max_value=20,
        initial=8,
        required=False,
    )
    blink = forms.IntegerField(
        min_value=0,
        max_value=10,
        initial=6,
        required=False,
    )
    rotation = forms.IntegerField(
        min_value=-15,
        max_value=15,
        initial=0,
        required=False,
    )
    scale = forms.IntegerField(
        min_value=800,
        max_value=1040,
        initial=980,
        required=False,
    )
    angle = forms.IntegerField(
        min_value=-44,
        max_value=45,
        initial=0,
        required=False,
    )

    def clean_shape(self):
        shape = self.cleaned_data.get("shape")
        if not shape:
            return "circle"
        return shape

    def clean_cols(self):
        return self.cleaned_data.get("cols") or 80

    def clean_max_radius(self):
        return self.cleaned_data.get("max_radius") or 8

    def clean_blink(self):
        val = self.cleaned_data.get("blink")
        return 6 if val is None else val

    def clean_rotation(self):
        val = self.cleaned_data.get("rotation")
        return 0 if val is None else val

    def clean_scale(self):
        val = self.cleaned_data.get("scale")
        return 980 if val is None else val

    def clean_angle(self):
        val = self.cleaned_data.get("angle")
        return 0 if val is None else val
