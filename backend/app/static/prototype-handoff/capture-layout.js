// Run in the page console, then save the returned object as JSON. No text/input values.
async function capturePrototypeLayout(landmarks) {
  await document.fonts.ready;
  const properties = ['display', 'position', 'boxSizing', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft',
    'marginTop', 'marginRight', 'marginBottom', 'marginLeft', 'gap', 'rowGap', 'columnGap', 'alignItems', 'justifyContent',
    'gridTemplateColumns', 'fontFamily', 'fontSize', 'fontWeight', 'lineHeight', 'letterSpacing', 'borderRadius',
    'maxWidth', 'minWidth', 'overflowX', 'overflowY'];
  const elements = {};
  for (const [key, selector] of Object.entries(landmarks)) {
    const matches = [...document.querySelectorAll(selector)].filter(el => el.getClientRects().length);
    if (matches.length !== 1) throw Error(`${key}: expected one visible landmark; got ${matches.length}`);
    const element = matches[0], rect = element.getBoundingClientRect(), style = getComputedStyle(element);
    elements[key] = { rect: Object.fromEntries(['x', 'y', 'width', 'height'].map(k => [k, Math.round(rect[k] * 100) / 100])),
      style: Object.fromEntries(properties.map(k => [k, style[k]])) };
  }
  return { viewport: { width: innerWidth, height: innerHeight }, devicePixelRatio,
    rootFontSize: getComputedStyle(document.documentElement).fontSize, scroll: { x: scrollX, y: scrollY },
    fonts: document.fonts.status, elements };
}
