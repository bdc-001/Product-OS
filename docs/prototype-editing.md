# Precise prototype changes

In Prototype, optionally name the target screen or control, then describe the intended
behavior. For example: “Campaign wizard → Retry configuration. Add a daily-attempt limit
that accepts 1–10, shows validation outside that range, and retains the value across tabs.”
When prompting from Code without a target, the selected file is sent as the target.

The service sends complete current files, ranks screen names and quoted UI labels, and
follows local imports. It does not prepend unrelated campaign source or truncate a file
midway. Initial intent and recent turns remain available, but current code and the latest
instruction take precedence. A source-fetch round lets the model request omitted files.
The serialized payload budget includes all supplied files rather than cutting off the tail.

The model can return exact replacements. Every old block must match once; all replacements
are validated before merging any file. A mismatched block, unseen path, or concurrent manual
edit rejects the result and preserves existing files. Deliberate full-file rewrites remain
supported when complete current source was supplied. Changed paths appear in the reply.

These checks protect source integrity; they do not prove that generated behavior matches
every subjective requirement. Try the stated interaction in Preview. The model is instructed
to state what changed, how to exercise it, and any incomplete part without claiming tests ran.
