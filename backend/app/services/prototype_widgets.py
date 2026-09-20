"""Shared Sense-style widgets for the prototype sandbox. Do not import go_services."""

FILTER_BAR = r'''import { useState } from "react";

function SenseFilterBar({ fields, values, onChange, sort, sorts, onSort, trailing }) {
  const [open, setOpen] = useState("");
  const [more, setMore] = useState(false);
  const primary = fields.filter((field) => field.primary);
  const extra = fields.filter((field) => !field.primary);
  const shown = more ? fields : (primary.length ? primary : fields.slice(0, 3));

  function selected(field) {
    return values[field.key] || [];
  }

  function toggle(field, option) {
    const cur = selected(field);
    const next = cur.includes(option.value)
      ? cur.filter((item) => item !== option.value)
      : cur.concat([option.value]);
    const copy = {};
    Object.keys(values).forEach((key) => {
      copy[key] = values[key];
    });
    fields.forEach((item) => {
      if (!(item.key in copy)) copy[item.key] = [];
    });
    copy[field.key] = next;
    onChange(copy);
  }

  function clearAll() {
    const empty = {};
    fields.forEach((field) => {
      empty[field.key] = [];
    });
    onChange(empty);
  }

  const count = fields.reduce((sum, field) => sum + selected(field).length, 0);

  return (
    <div className="filter-bar">
      <div className="filter-row">
        {shown.map((field) => (
          <div key={field.key} className="filter-pop">
            <button
              type="button"
              className={selected(field).length ? "chip on" : "chip"}
              onClick={() => setOpen(open === field.key ? "" : field.key)}
            >
              {field.label}
              {selected(field).length ? <em>{selected(field).length}</em> : null}
              <span className="caret">▾</span>
            </button>
            {open === field.key ? (
              <div className="filter-menu">
                {field.group ? <p className="filter-group">{field.group}</p> : null}
                {field.options.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    className={selected(field).includes(opt.value) ? "filter-opt on" : "filter-opt"}
                    onClick={() => toggle(field, opt)}
                  >
                    <span className="check">{selected(field).includes(opt.value) ? "✓" : ""}</span>
                    {opt.label}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        ))}
        {extra.length ? (
          <button type="button" className={more ? "chip on" : "chip"} onClick={() => setMore(!more)}>
            More filters
          </button>
        ) : null}
        {sorts && sorts.length ? (
          <div className="filter-pop">
            <button type="button" className="chip" onClick={() => setOpen(open === "sort" ? "" : "sort")}>
              Sort
              <span className="caret">▾</span>
            </button>
            {open === "sort" ? (
              <div className="filter-menu">
                {sorts.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    className={sort === opt.value ? "filter-opt on" : "filter-opt"}
                    onClick={() => onSort && onSort(opt.value)}
                  >
                    <span className="check">{sort === opt.value ? "✓" : ""}</span>
                    {opt.label}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
        {count ? (
          <button type="button" className="chip ghost" onClick={clearAll}>
            Clear filters
          </button>
        ) : null}
        <div className="filter-trail">{trailing}</div>
      </div>
    </div>
  );
}

export default SenseFilterBar;
'''
