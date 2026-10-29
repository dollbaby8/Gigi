"""Instagram-ready scene presets. {T} is replaced with the twin's trigger word.

The realism suffix is what keeps outputs from looking "AI glossy": phone-camera
optics, real skin texture, imperfect candid framing.
"""

REALISM = (
    "candid photo shot on iPhone 15 Pro, natural skin texture with visible pores, "
    "subtle imperfections, natural lighting, slight film grain, shallow depth of field, "
    "authentic unposed moment, no airbrushing, photorealistic"
)

PRESETS = {
    "river_oaks_brunch": "{T}, a woman in her early 30s, at an upscale River Oaks Houston brunch patio, "
    "linen blazer, gold jewelry, mimosa on the table, laughing mid-conversation, late morning sun",
    "courthouse_chic": "{T}, a woman in her early 30s, walking down courthouse steps in downtown Houston, "
    "tailored black suit, leather tote, confident stride, golden hour",
    "power_desk": "{T}, a woman in her early 30s, at a modern law office desk with a city skyline window, "
    "silk blouse, reading a document, coffee in hand, soft window light",
    "galleria_shopping": "{T}, a woman in her early 30s, carrying designer shopping bags in Houston's "
    "Post Oak area, sunglasses pushed up on head, chic casual outfit, street style photo",
    "gold_coast_throwback": "{T}, a woman in her early 30s, on Oak Street in Chicago's Gold Coast in fall, "
    "camel coat, cashmere scarf, brownstones behind her, crisp daylight",
    "nyc_weekend": "{T}, a woman in her early 30s, in SoHo New York City, cobblestone street, "
    "trench coat, iced coffee, candid street style",
    "date_night": "{T}, a woman in her early 30s, at a candlelit upscale restaurant, elegant black dress, "
    "warm ambient light, wine glass, soft smile, evening",
    "rooftop_sunset": "{T}, a woman in her early 30s, on a Houston rooftop bar at sunset, "
    "satin slip dress, skyline bokeh, wind in hair",
    "pilates_morning": "{T}, a woman in her early 30s, leaving a boutique pilates studio, matching "
    "athleisure set, water bottle, messy bun, bright morning light",
    "sunday_reset": "{T}, a woman in her early 30s, curled up on a cream sofa in a sunlit luxury apartment, "
    "oversized sweater, journal and latte, cozy, relaxed",
    "close_up_portrait": "{T}, close-up portrait of a woman in her early 30s, natural makeup, "
    "soft window light, looking just past the camera",
}


def build_prompt(text: str, trigger: str) -> str:
    text = text.replace("{T}", trigger)
    if trigger not in text:
        text = f"{trigger}, {text}"
    return f"{text}, {REALISM}"
