"""Channel-sized composition seeds for the reference-led designer.

These encode relationships, not fabricated product screens or decorative data.
The designer still polishes them and the rendered result still needs visual review.
"""
from html import escape


def esc(value):
    return escape(str(value or ""))


def symbol(kind):
    paths = {
        "call": '<path d="M30 20h60a12 12 0 0 1 12 12v42a12 12 0 0 1-12 12H55L33 103V86h-3a12 12 0 0 1-12-12V32a12 12 0 0 1 12-12Z"/><path d="M36 43h48M36 60h32"/>',
        "group": '<circle cx="28" cy="28" r="12"/><circle cx="90" cy="28" r="12"/><circle cx="28" cy="90" r="12"/><circle cx="90" cy="90" r="12"/><circle cx="60" cy="59" r="17"/><path d="m37 37 10 10m26-1 8-9M37 81l11-10m23 2 10 9"/>',
        "patch": '<path d="M30 13h43l20 20v75H30Z"/><path d="M73 13v23h20M45 54h32M45 70h32M45 87h21"/><path d="m77 89 7 7 15-17"/>',
        "clock": '<circle cx="60" cy="60" r="43"/><path d="M60 30v33l22 12"/>',
        "play": '<circle cx="60" cy="60" r="43"/><path d="m50 40 30 20-30 20Z"/>',
    }
    return '<svg viewBox="0 0 120 120" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + paths[kind] + '</svg>'


def carousel_seed(content):
    slides = content["slides"]
    pages = []
    for index, slide in enumerate(slides):
        points = slide.get("points") or []
        dark = slide["layout"] in {"hook", "cta"}
        logo = "{{brand_on_dark}}" if dark else "{{brand_on_light}}"
        style = slide["visual"]
        if slide["layout"] == "hook":
            labels = points[:3]
            nodes = ''.join(f'<div class="orbit-node">{symbol(["call","group","patch"][i])}<b>{esc(p)}</b></div>' + ('<span class="link-arrow">→</span>' if i < len(labels)-1 else '') for i,p in enumerate(labels))
            visual = f'<div class="orbit">{nodes}</div>'
        elif slide["layout"] == "cta":
            visual = '<div class="offer">' + ''.join(f'<div class="offer-row">{symbol("clock" if i == 0 else "play")}<b>{esc(p)}</b></div>' for i,p in enumerate(points)) + '</div>'
        elif style == "steps":
            visual = '<div class="path">' + ''.join(f'<div class="path-row"><span class="step">{i+1}</span><div class="path-icon">{symbol(["clock","call","group"][i%3])}</div><b>{esc(p)}</b></div>' for i,p in enumerate(points)) + '</div>'
        elif style == "contrast":
            # Show two genuine alternatives. Iconography is a conceptual representation.
            visual = '<div class="comparison">' + ''.join(f'<div class="comparison-side side-{i}"><div class="device">{symbol("patch" if slide["layout"] == "proof" else "call" if i == 0 else "group")}</div><b>{esc(p)}</b></div>' for i,p in enumerate(points[:2])) + '</div>'
            if slide["layout"] == "proof":
                visual += '<div class="decision-line"><span>Approve</span><i>or</i><span>Decline</span></div>' if 'approve' in slide['body'].lower() and 'decline' in slide['body'].lower() else ''
        else:
            visual = '<div class="branches"><div class="hub">' + symbol('group') + '</div><div class="branch-items">' + ''.join(f'<div class="branch-row"><span class="severity-dot level-{i}"></span><b>{esc(p)}</b></div>' for i,p in enumerate(points)) + '</div></div>'
        pages.append(f'''<section class="page {"dark" if dark else "light"} {esc(slide["layout"])}">
        <header><img src="{logo}" alt="{{{{brand_name}}}}"><span style="text-transform:uppercase">{{{{brand_module}}}}</span></header>
        <main><h1>{esc(slide["headline"])}</h1><p class="dek">{esc(slide["body"])}</p><div class="visual">{visual}</div></main>
        <footer><span>{{{{brand_name}}}}</span><span>{index+1:02} / {len(slides):02}</span></footer></section>''')
    return '''<!doctype html><html><head><meta charset="utf-8"><style>
    *{box-sizing:border-box}body{margin:0}.page{width:1080px;height:1350px;overflow:visible;font-family:Inter,Arial,sans-serif;position:relative}
    .dark{color:#f7faff;background:radial-gradient(ellipse at 100% 85%,#1658e1 0,transparent 65%),#081e4c}.light{background:#fff;color:#0a2e7a}
    header{height:158px;padding:66px 64px 40px;display:flex;align-items:center;justify-content:space-between}header img{height:30px}header span{font-size:20px;letter-spacing:3px}
    main{padding:20px 64px 0;height:1080px}h1{font-family:Helvetica Neue,Arial,sans-serif;font-size:84px;line-height:1.07;letter-spacing:-3px;margin:0;max-width:952px}
    .dek{font-size:29px;line-height:1.45;margin:30px 0 0;max-width:900px;color:#405576}.dark .dek{color:#c9daff}.hook h1,.cta h1{font-size:94px;line-height:1.06;letter-spacing:-3.8px}
    .visual{margin-top:64px;height:580px;display:flex;flex-direction:column;justify-content:center;position:relative}.visual svg{display:block;width:128px;height:128px}
    footer{height:112px;position:absolute;left:0;right:0;bottom:0;padding:40px 64px;display:flex;justify-content:space-between;align-items:center;border-top:1px solid #d1e1fd;font-size:18px;letter-spacing:2px;background:#fff;color:#0a2e7a}.dark footer{background:#081e4c;color:#afcafb;border-color:#28436b}
    .orbit{display:flex;align-items:center;gap:18px;padding:52px 0;position:relative}.orbit-node{flex:1;min-width:0;border:1px solid #5079c4;border-radius:150px 150px 24px 24px;min-height:344px;padding:46px 22px 32px;background:#ffffff09;display:flex;flex-direction:column;align-items:center;text-align:center;gap:40px}.orbit-node:nth-of-type(3){background:#1a62f2;border-color:#7da8f8}.orbit-node svg{color:#5fe6eb}.orbit-node b{font-size:29px;line-height:1.25}.link-arrow{font-size:38px;color:#5fe6eb}
    .path{position:relative;display:grid;gap:0}.path:before{content:"";position:absolute;left:48px;top:80px;bottom:80px;width:2px;background:#afcafb}.path-row{height:174px;display:flex;align-items:center;gap:30px;position:relative;border-bottom:1px solid #d1e1fd}.path-row:last-child{border-bottom:0}.step{width:98px;height:98px;flex-shrink:0;border-radius:50%;display:grid;place-items:center;background:#1a62f2;color:white;font-size:42px}.path-icon{width:100px;flex-shrink:0;color:#1658e1}.path-icon svg{width:86px;height:86px}.path-row b{font-size:40px;line-height:1.2}
    .comparison{display:grid;grid-template-columns:1fr 1fr;gap:28px}.comparison-side{min-height:430px;padding:40px;border:1px solid #afcafb;border-radius:24px;background:#eef4ff}.comparison-side.side-1{background:#0a2e7a;color:white;border-color:#0a2e7a}.device{margin-bottom:44px}.device svg{width:162px;height:162px}.comparison-side b{font-size:40px;line-height:1.16;display:block}.decision-line{display:flex;gap:30px;justify-content:center;align-items:center;margin-top:30px;font-size:29px}.decision-line span{border:1px solid #afcafb;border-radius:40px;padding:15px 34px}.decision-line i{font-size:24px;color:#6a6a6a}
    .branches{display:flex;align-items:center;gap:64px}.hub{width:260px;height:260px;display:grid;place-items:center;border:1px solid #afcafb;border-radius:50%;background:#eef4ff;flex-shrink:0}.hub svg{width:168px;height:168px}.branch-items{flex:1;border-left:2px solid #afcafb;padding-left:42px}.branch-row{height:142px;display:flex;align-items:center;gap:28px;border-bottom:1px solid #d1e1fd;position:relative}.branch-row:before{content:"";position:absolute;left:-42px;top:70px;width:42px;height:2px;background:#afcafb}.branch-row:last-child{border:0}.branch-row b{font-size:48px;text-transform:capitalize}.severity-dot{width:28px;height:28px;border-radius:50%;background:#afcafb}.level-1{background:#4a84f5}.level-2{background:#0a2e7a}
    .offer{display:grid;gap:28px}.offer-row{border-top:1px solid #5079c4;padding:34px 0;display:flex;align-items:center;gap:40px}.offer-row svg{width:108px;height:108px;flex-shrink:0;color:#5fe6eb}.offer-row b{font-size:40px;line-height:1.2}.cta .visual{height:450px;margin-top:52px}
    </style></head><body>''' + ''.join(pages) + '</body></html>'
