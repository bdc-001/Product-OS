from PIL import Image
import pytest

from app.services.marketing_film_gates import (
    STATEMENT_TREATMENTS, TRANSITIONS, assert_encode_density, craft_for_scenes,
    measure_frame, measure_sequence,
)
from app.services import marketing_video as video
from pathlib import Path


def brand_frame(size=(160, 90), shift=0):
    image = Image.new('RGB', size)
    pixels = image.load()
    width, height = size
    orb_x = 20 + (shift % (width - 40))
    for y in range(height):
        for x in range(width):
            tone = x / width
            red, green, blue = int(26 + 180 * tone), int(48 + 40 * (y / height)), int(242 - 120 * tone)
            dx, dy = x - orb_x, y - height / 2
            if dx * dx + dy * dy < 28 * 28:
                red, green, blue = 26, 98, 242
            pixels[x, y] = (red, green, blue)
    return image


def test_craft_rotates_statement_treatments_and_transitions():
    scenes = [{'visual': 'statement'} for _ in range(3)]
    craft = craft_for_scenes(scenes)
    assert [item['treatment'] for item in craft] == list(STATEMENT_TREATMENTS)
    assert [item['luma'] for item in craft] == ['dark', 'light', 'dark']
    assert [item['transition'] for item in craft] == list(TRANSITIONS[:3])
    assert all(item['plate'] is None for item in craft)


def test_device_shots_stay_on_a_light_stage_without_a_plate_under_black_chrome():
    scenes = [{'visual': 'call'} for _ in range(4)] + [{'visual': 'flow'}]
    craft = craft_for_scenes(scenes)
    assert {item['treatment'] for item in craft[:4]} == {'stage-light'}
    assert all(item['luma'] == 'light' for item in craft[:4])
    assert all(item['plate'] is None for item in craft[:4])
    assert craft[4]['plate'] == 'signal-flow.jpg'


def test_consecutive_same_type_cannot_reuse_a_treatment():
    scenes = [{'visual': 'contrast'}, {'visual': 'contrast'}, {'visual': 'steps'}, {'visual': 'steps'}]
    craft = craft_for_scenes(scenes)
    assert craft[0]['treatment'] != craft[1]['treatment']
    assert craft[2]['luma'] != craft[3]['luma']
    assert {item['transition'] for item in craft} == set(TRANSITIONS)


def test_blank_and_grey_frames_fail_saturation_and_luma_gates():
    white = measure_frame(Image.new('RGB', (160, 90), (255, 255, 255)))
    grey = measure_frame(Image.new('RGB', (160, 90), (180, 180, 180)))
    brand = measure_frame(brand_frame())
    assert not white['passed'] and any('luma' in issue or 'saturation' in issue for issue in white['issues'])
    assert not grey['passed']
    assert brand['passed'], brand


def test_identical_hold_and_empty_bitrate_fail():
    frozen = [brand_frame() for _ in range(4)]
    report = measure_sequence(frozen, fps=2)
    assert not report['passed']
    assert any('identical-frame' in issue for issue in report['issues'])
    moving = [brand_frame(shift=i * 40) for i in range(6)]
    assert measure_sequence(moving, fps=2)['passed']
    with pytest.raises(ValueError, match='bitrate'):
        assert_encode_density({'streams': [
            {'codec_type': 'video', 'width': 1920, 'height': 1080, 'bit_rate': '200000'},
            {'codec_type': 'audio', 'bit_rate': '192000'},
        ], 'format': {'bit_rate': '392000'}}, 'landscape')
    assert assert_encode_density({'streams': [
        {'codec_type': 'video', 'width': 1920, 'height': 1080, 'bit_rate': '4500000'},
        {'codec_type': 'audio', 'bit_rate': '192000'},
    ], 'format': {'bit_rate': '4692000'}}, 'landscape')['passed']


def test_design_contract_encodes_world_architecture_and_numeric_gates():
    contract = (Path(video.__file__).resolve().parents[2] / 'app/static/artifacts/marketing-video-design.md').read_text()
    for needle in ('persistent world', 'never remounted', '1.8 Mbps', '220 kbps', 'identical-frame', 'three motion', 'No flat fills', 'photographic', 'iPhone', 'stage-light', 'lockup polarity'):
        assert needle.lower() in contract.lower()
    world = (video.REMOTION_DIR / 'src/marketing/World.tsx').read_text()
    assert 'PersistentWorld' in world and 'CROSS_FRAMES' in world and 'stage-light' in world
    for name in ('Film.tsx', 'PiiCallFirst.tsx', 'PiiLaunch.tsx', 'PiiFilm.tsx'):
        source = (video.REMOTION_DIR / 'src/marketing' / name).read_text()
        assert 'FilmRoot' in source and 'SceneLayer' in source
    call_first = (video.REMOTION_DIR / 'src/marketing/PiiCallFirst.tsx').read_text()
    cards = (video.REMOTION_DIR / 'src/marketing/kit/Cards.tsx').read_text()
    assert 'PersistentCall' in call_first and 'IPhone' in call_first and 'PaymentCard' in call_first
    assert 'CALL_HEADER' in call_first and 'spokenLine' in call_first
    assert 'Spoken' not in call_first and 'inset 0 -3px' not in call_first
    assert "color:note" in call_first and "mask?B" not in call_first
    assert 'Protect the private detail' in call_first
    assert 'rotateY' not in cards and 'INCOME TAX DEPARTMENT' in cards and 'VALID THRU' in cards
    assert .96 <= video.AGENT_VOICE['speed'] <= 1.05
    assert video.CUSTOMER_VOICE.get('line') == 'handset'
