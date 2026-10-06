"""Real Chromium/PDF regressions: geometry must survive print reference CSS."""
import fitz
import pytest
from PIL import Image
from app.services.marketing_design import render_design


def test_landscape_export_overrides_reference_a4_and_keeps_rightmost_copy(tmp_path):
    content = {"title": "Agent Monitoring", "dek": "Review the suggested change."}
    html = '''<html><head><style>
      @page { size:A4; margin:0 } * {box-sizing:border-box}
      .page {width:1600px;height:900px;position:relative;background:#102342;color:white}
      h1 {position:absolute;left:60px;top:50px;font:60px Arial}
      p {position:absolute;left:1220px;top:500px;width:320px;font:32px Arial}
      .glow {position:absolute;left:-100px;top:-100px;width:300px;height:300px;background:#1a62f2}
    </style></head><body><section class="page"><div class="glow"></div>
      <h1>Agent Monitoring</h1><p>Review the suggested change.</p>
    </section></body></html>'''
    render_design("feature_image", content, html, tmp_path)
    with fitz.open(tmp_path / "feature_image.pdf") as pdf:
        assert len(pdf) == 1
        assert abs(pdf[0].rect.width - 1200) < 2
        assert abs(pdf[0].rect.height - 675) < 2
        assert "Review the suggested change." in " ".join(pdf[0].get_text().split())
    with Image.open(tmp_path / "feature_image-01.png") as png:
        assert png.size == (1600, 900)


def test_text_clipped_by_a_band_is_rejected_even_inside_page(tmp_path):
    html = '''<html><head><style>.page{width:1600px;height:900px}
    .band{height:20px;overflow:hidden}h1{margin:0;font:60px Arial}</style></head>
    <body><section class="page"><div class="band"><h1>Agent Monitoring</h1></div></section></body></html>'''
    with pytest.raises(ValueError, match="exceeds"):
        render_design("feature_image", {"title": "Agent Monitoring"}, html, tmp_path)


def test_manual_print_preserves_ordered_steps_and_wrapped_hyphens(tmp_path):
    from app.services.marketing_manual import manual_design
    from app.services.marketing_design import render_flowing_document, normalized_copy
    content = {"title": "Agent Monitoring", "dek": "", "cta": "Review the findings.",
        "sections": [{"role": "overview", "heading": "Overview", "body": "Review the agent's recent runs."},
                     {"role": "workflow", "heading": "Workflow", "body": "1. Open the agent.\n2. Review its root-cause groups."},
                     {"role": "action", "heading": "Action", "body": "- Read the proposed change.\n- Apply an approved patch."}]}
    render_flowing_document("release_notes", content, manual_design(content), tmp_path)
    html = manual_design(content)
    assert "Nunito" in html
    assert "<img" not in html
    assert "<h2>Overview</h2>" not in html and "<ul>" in html
    with fitz.open(tmp_path / "release_notes.pdf") as pdf:
        text = " ".join(page.get_text() for page in pdf)
        assert all(page.get_images() for page in pdf)  # Repeated Acme header survives export.
    assert 'Read the proposed change.' in text and 'Apply an approved patch.' in text
    assert "1. open the agent. 2. review its root-cause groups." in normalized_copy(text)
    assert normalized_copy("root-\ncause") == "root-cause"


def test_two_page_preview_gutter_does_not_create_extra_pdf_pages(tmp_path):
    source = '''<html><head><style>*{box-sizing:border-box}
    .page{width:794px;height:1123px;position:relative;background:#fff}
    .page+.page{margin-top:22px}h1{margin:0;padding:30px}
    footer{position:absolute;bottom:20px;left:30px}
    </style></head><body><section class="page"><h1>Agent Monitoring</h1></section>
    <section class="page"><footer>Review the proposed patch.</footer></section></body></html>'''
    render_design("article", {"title":"Agent Monitoring","cta":"Review the proposed patch."}, source, tmp_path)
    with fitz.open(tmp_path / "article.pdf") as document:
        assert len(document) == 2
        assert "Review the proposed patch." in document[1].get_text()


def test_footer_cannot_cover_copy_that_pdf_text_extraction_still_finds(tmp_path):
    source = '''<html><head><style>.page{width:794px;height:1123px;position:relative}
    p{position:absolute;bottom:15px;left:30px}footer{position:absolute;bottom:0;height:70px;width:100%;background:navy}
    </style></head><body><section class="page"><p>Review the proposed patch.</p><footer></footer></section></body></html>'''
    with pytest.raises(ValueError, match="covered by its footer"):
        render_design("feature_brief", {"cta":"Review the proposed patch."}, source, tmp_path)


def test_four_node_manual_figure_keeps_nunito_heading_and_nodes_inside_canvas(tmp_path):
    from app.services.marketing_manual import render_manual_figures
    content = {'figures': [{'kind': 'flow', 'heading': 'From calls to a reviewed prompt patch',
        'items': [{'lead': lead, 'text': text} for lead, text in [
            ('Recent calls', 'Evaluates recent interactions'),
            ('Root causes', 'Groups failures by root cause'),
            ('Suggested patch', 'Proposes a prompt change'),
            ('Review and apply', 'Review, approve, then apply')]]}]}
    files = render_manual_figures(content, tmp_path)
    assert files == [('release_notes-figure-01.png', 'image/png')]
    with Image.open(tmp_path / files[0][0]) as figure:
        assert figure.size == (1400, 510)


def test_cta_box_cannot_cross_footer_even_when_its_text_clears_it(tmp_path):
    source = '''<html><head><style>.page{width:794px;height:1123px;position:relative}
    .cta{position:absolute;bottom:50px;height:100px;width:500px;background:#eef4ff}
    footer{position:absolute;bottom:0;height:70px;width:100%;border-top:1px solid blue}
    </style></head><body><section class="page"><div class="cta">Review the proposed patch.</div><footer></footer></section></body></html>'''
    with pytest.raises(ValueError, match='covered by its footer'):
        render_design('feature_brief', {'cta':'Review the proposed patch.'}, source, tmp_path)
