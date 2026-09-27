"""
Сервис генерации гипнотических названий для картин галереи.

Включает:
- Локальный генератор псевдослучайных гипно-заголовков (в стиле Гипножабы, психоделики и мемов).
- Закладку (интерфейс и спецификацию) для будущей интеграции с OpenRouter API (мультимодальные VLM).
"""

import random
from typing import Optional


# Словари для локального генератора гипно-тайтлов на английском языке
HYPNO_ADJECTIVES = [
    "Shimmering", "Astral", "Hypnotic", "Vulgar", "Surreal", "Absurd", "Psyche&shy;delic",
    "Pulsating", "Neon", "Trans&shy;cendent", "Cerebral", "Mental", "Subcon&shy;scious", "Cosmic",
    "Halluci&shy;nogenic", "Fractal", "Detached", "Synes&shy;thetic", "Parallel", "Illusory", "Ephemeral",
    "Hypnot&shy;oadian", "Conductive", "Mesme&shy;rizing", "Magnetic", "Carefree", "Oneiric",
    "Psychot&shy;ropic", "Mystical", "Other&shy;worldly", "Spiral", "Quivering", "Slippery", "Misty",
    "Ethereal", "Trance", "Quantum", "Juicy", "Hypno-Absurd", "Psychoactive", "Magical",
    "Synthetic", "Chromatic", "Perceptive", "Perforated", "Vibra&shy;tional", "Neural",
    "Subliminal", "Glitched", "Radioactive", "Brain-Melting", "Galactic", "Phospho&shy;rescent",
    "Chaotic", "Hypnagogic", "Interdim&shy;ensional", "Cybernetic", "Uncanny",
]

HYPNO_NOUNS = [
    "Trance", "Pulsar", "Gaze", "Brain Slug", "Vortex", "Portal", "Path", "Fractal", "Signal", "Spectrum",
    "Resonance", "Mirage", "Oasis", "Abyss", "Labyrinth", "Impulse", "Monolith", "Oracle", "Vector",
    "Clot", "Cascade", "Horizon", "Toadstool", "Pattern", "Contour", "Phantom", "Splash", "Tranqui&shy;lizer",
    "Mist", "Crystal", "Stream", "Singulator", "Pulse", "Glitch", "Synthesis", "Roar", "Tremor",
    "Frontier", "Sentinel", "Gatekeeper", "Whisper", "Spore", "Worm", "Bubble", "Psycho-Spider",
    "Receptor", "Mind-Warp", "Hypnotoad", "Neuron", "Oscil&shy;lation", "Echo", "Hologram", "Matrix",
    "Mind-drill", "Neurotoxin", "Dreamscape", "Substance",
]

HYPNO_GENITIVES = [
    "of&nbsp;Consciousness", "of&nbsp;the&nbsp;Hypnotoad", "of&nbsp;the&nbsp;Subcon&shy;scious",
    "of&nbsp;the&nbsp;Void", "of&nbsp;the&nbsp;Matrix", "of&nbsp;the&nbsp;Psycho-Web", "of&nbsp;the&nbsp;Brain Slug",
    "of&nbsp;the&nbsp;Noosphere", "of&nbsp;the&nbsp;Neo-Modern", "of&nbsp;the&nbsp;Deep Trance",
    "of&nbsp;the&nbsp;Ether", "of&nbsp;the&nbsp;4th Dimension", "of&nbsp;Pointillism", "of&nbsp;the&nbsp;Substance",
    "of&nbsp;Uncer&shy;tainty", "of&nbsp;the&nbsp;Continuum", "of&nbsp;Acid", "of&nbsp;Pure Perception",
    "of&nbsp;Lucid Dreams", "of&nbsp;Halluci&shy;nations", "of&nbsp;Psyche&shy;delia", "of&nbsp;Trans&shy;cendence",
    "of&nbsp;the&nbsp;Nether&shy;world", "of&nbsp;DOOP Regul&shy;ations", "of&nbsp;Galactic Frequencies",
    "of&nbsp;Grade&nbsp;24 Bureaucracy",
]

HYPNO_POSTFIXES = [
    "#42", "v3.14", "(Ultra)", "(Phase&nbsp;7)", "(Alpha)", "(Omega)", "(Protocol&nbsp;09)", "(Revision&nbsp;14)",
    "(Extract)", "(Layer&nbsp;9)", "(Ward&nbsp;106)", "(Hangar&nbsp;18)", "(Unfinished Opus)", "(Secret Project)",
    "[Classified]", "(DOOP-66)", "(Sub-Level&nbsp;4)", "(MK-Ultra)", "С90"
]


def generate_hypno_title(seed: Optional[int] = None) -> str:
    """
    Генерирует сочное гипнотическое название для картины на основе словарей.
    Примеры:
    - «Hypnotic Pulsar of the Hypnotoad #42»
    - «Astral Gaze»
    - «Brain Slug of the Void»
    - «Transcendent (Ultra)»
    - «Hypnotic»
    - «Vortex»
    """
    rng = random.Random(seed)
    adj = rng.choice(HYPNO_ADJECTIVES)
    noun = rng.choice(HYPNO_NOUNS)
    genitive = rng.choice(HYPNO_GENITIVES)
    postfix = rng.choice(HYPNO_POSTFIXES)

    patterns = [
        # Однословные варианты
        lambda: noun,
        lambda: adj,
        # Двухсловные комбинации
        lambda: f"{adj} {noun}",
        lambda: f"{noun} {genitive}",
        lambda: f"{noun} {postfix}",
        lambda: f"{adj} {postfix}",
        # Трех- и четырехсловные гипно-конструкции
        lambda: f"{adj} {noun} {genitive}",
        lambda: f"{adj} {noun} {postfix}",
        lambda: f"{adj} {noun} {genitive} {postfix}",
    ]

    chosen_pattern = rng.choice(patterns)
    return chosen_pattern()


# =====================================================================
# ЗАКЛАДКА: OpenRouter VLM API Integration (Post-MVP / AI Title)
# =====================================================================
def generate_title_openrouter(
    image_bytes: bytes,
    *,
    api_key: Optional[str] = None,
    model: str = "google/gemini-2.5-flash",
    system_prompt: str = (
        "You are the herald of the almighty Hypnotoad. Create a short (2-4 words), "
        "punchy, ironically absurd, and hypnotic English title "
        "for a halftone SVG artwork shown in the thumbnail. "
        "Reply ONLY with the title, without quotes or introductory words."
    ),
    timeout: int = 5,
) -> Optional[str]:
    """
    [ЗАКЛАДКА ПОД OPENROUTER API]
    
    Спецификация интеграции:
    1. Исходное растровое изображение сжимается до thumbnail 256x256 WebP/JPEG.
    2. Кодируется в Base64 (data:image/jpeg;base64,...).
    3. Отправляется POST-запрос на https://openrouter.ai/api/v1/chat/completions:
       Payload: {
           "model": model,
           "messages": [
               {"role": "system", "content": system_prompt},
               {
                   "role": "user",
                   "content": [
                       {"type": "text", "text": "Give a hypnotic title for this artwork:"},
                       {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_data}"}}
                   ]
               }
           ],
           "max_tokens": 50,
           "temperature": 0.9
       }
    4. При ошибке таймаута, отсутствии OPENROUTER_API_KEY в .env или сбое сети 
       функция возвращает None, вызывая локальный fallback (generate_hypno_title).
    """
    # TODO: Интегрировать requests / httpx при добавлении OPENROUTER_API_KEY в settings.py
    if not api_key:
        return None
    
    # Заглушка: при отсутствии реального сетевого коннектора возвращаем None для fallback
    return None
