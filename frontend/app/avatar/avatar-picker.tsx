"use client";

import AddAPhotoOutlinedIcon from "@mui/icons-material/AddAPhotoOutlined";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import PersonOutlineRoundedIcon from "@mui/icons-material/PersonOutlineRounded";
import RefreshRoundedIcon from "@mui/icons-material/RefreshRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import Box from "@mui/material/Box";
import ButtonBase from "@mui/material/ButtonBase";
import CircularProgress from "@mui/material/CircularProgress";
import IconButton from "@mui/material/IconButton";
import InputAdornment from "@mui/material/InputAdornment";
import MenuItem from "@mui/material/MenuItem";
import Skeleton from "@mui/material/Skeleton";
import TextField from "@mui/material/TextField";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { DropZone, errorText, mk } from "@/app/avatar/shared";
import { AppDialog, Banner, PillButton, Segmented } from "@/app/ui";
import { apple, pmm } from "@/app/ui/tokens";
import { avatarApi, type AvatarLook, type CreatedAvatar } from "@/lib/avatar";

const MAX_PHOTOS = 8;
const MAX_PHOTO_BYTES = 20 * 1024 * 1024;

function typeLabel(type: string) {
  if (type === "photo_avatar") return "Photo avatar";
  if (type === "digital_twin") return "Digital twin";
  if (type === "studio_avatar") return "Studio avatar";
  return type ? type.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase()) : "Avatar";
}

function lookStatus(status: string) {
  if (["pending", "processing", "training", "in_progress"].includes(status)) return "Training";
  if (status === "failed") return "Failed";
  return status ? status.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase()) : "Not ready";
}

function LookTile({ look, selected, onPick, onCheck, checking }: { look: AvatarLook; selected: boolean; onPick: () => void; onCheck?: () => void; checking?: boolean }) {
  const tile = (
    <ButtonBase
      onClick={onPick}
      disabled={!look.ready}
      aria-pressed={selected}
      aria-label={look.ready ? look.name : `${look.name}, ${lookStatus(look.status).toLowerCase()}`}
      sx={{
        display: "block",
        width: "100%",
        textAlign: "left",
        borderRadius: "14px",
        overflow: "hidden",
        border: `1.5px solid ${selected ? mk.main : apple.hairline}`,
        boxShadow: selected ? `0 0 0 3px ${mk.fill}` : "none",
        bgcolor: apple.raised,
        transition: `border-color 0.2s ${apple.smooth}, box-shadow 0.2s ${apple.smooth}, transform 0.3s ${apple.pop}`,
        "&:hover": { borderColor: selected ? mk.main : apple.hairlineHover, transform: "translateY(-1px)" },
        "&.Mui-focusVisible": { outline: `2px solid ${apple.ink}`, outlineOffset: 2 },
        "&.Mui-disabled": { cursor: "default" },
      }}
    >
      <Box sx={{ position: "relative", aspectRatio: "3 / 4", bgcolor: apple.hoverFill }}>
        {look.preview_image_url ? (
          <Box
            component="img"
            src={look.preview_image_url}
            alt=""
            loading="lazy"
            sx={{ width: "100%", height: "100%", objectFit: "cover", display: "block", filter: look.ready ? "none" : "grayscale(0.7)", opacity: look.ready ? 1 : 0.55 }}
          />
        ) : (
          <Box sx={{ display: "grid", placeItems: "center", height: "100%", color: apple.muted }}>
            <PersonOutlineRoundedIcon />
          </Box>
        )}
        {selected ? <CheckCircleRoundedIcon sx={{ position: "absolute", top: 8, right: 8, color: mk.main, bgcolor: apple.page, borderRadius: "50%", fontSize: 22 }} /> : null}
      </Box>
      <Box sx={{ px: 1.1, py: 0.9 }}>
        <Typography noWrap sx={{ fontSize: 12.5, fontWeight: 600, color: apple.text }}>
          {look.name}
        </Typography>
        <Typography noWrap sx={{ fontSize: 11.5, color: look.ready ? apple.muted : look.status === "failed" ? apple.danger : pmm.amber }}>
          {look.ready ? typeLabel(look.avatar_type) : lookStatus(look.status)}
        </Typography>
      </Box>
    </ButtonBase>
  );
  return (
    <Box sx={{ position: "relative", minWidth: 0 }}>
      {look.error ? <Tooltip title={look.error}>{tile}</Tooltip> : tile}
      {!look.ready && onCheck ? (
        <Tooltip title="Check training status">
          <IconButton size="small" onClick={onCheck} disabled={checking} aria-label={`Check status of ${look.name}`} sx={{ position: "absolute", top: 6, right: 6, bgcolor: apple.page, "&:hover": { bgcolor: apple.page } }}>
            {checking ? <CircularProgress size={14} /> : <RefreshRoundedIcon sx={{ fontSize: 16 }} />}
          </IconButton>
        </Tooltip>
      ) : null}
    </Box>
  );
}

export function AvatarPicker({ selectedId, onPick, disabled }: { selectedId: string; onPick: (look: AvatarLook) => void; disabled?: boolean }) {
  const [ownership, setOwnership] = useState<"private" | "public">("private");
  const [items, setItems] = useState<AvatarLook[] | null>(null);
  const [next, setNext] = useState("");
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("");
  const [more, setMore] = useState(false);
  const [checking, setChecking] = useState("");
  const [creating, setCreating] = useState(false);
  const request = useRef(0);

  const load = useCallback(async (owner: "private" | "public", fresh = false) => {
    const id = ++request.current;
    setItems(null);
    setError("");
    try {
      const page = await avatarApi.avatars(owner, "", fresh);
      if (id !== request.current) return;
      setItems(page.items);
      setNext(page.has_more ? page.next_token : "");
    } catch (err) {
      if (id !== request.current) return;
      setItems([]);
      setNext("");
      setError(errorText(err, "Could not load avatars from HeyGen."));
    }
  }, []);

  useEffect(() => {
    void load(ownership);
  }, [load, ownership]);

  const loadMore = async () => {
    if (!next) return;
    setMore(true);
    try {
      const page = await avatarApi.avatars(ownership, next);
      setItems((current) => [...(current || []), ...page.items.filter((item) => !(current || []).some((existing) => existing.id === item.id))]);
      setNext(page.has_more ? page.next_token : "");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setMore(false);
    }
  };

  const check = async (look: AvatarLook) => {
    setChecking(look.id);
    try {
      const fresh = await avatarApi.look(look.id);
      setItems((current) => (current || []).map((item) => (item.id === fresh.id ? fresh : item)));
    } catch (err) {
      setError(errorText(err));
    } finally {
      setChecking("");
    }
  };

  const groups = useMemo(() => {
    const seen = new Map<string, string>();
    for (const item of items || []) if (item.group_id && !seen.has(item.group_id)) seen.set(item.group_id, item.name);
    return Array.from(seen, ([id, name]) => ({ id, name }));
  }, [items]);

  const needle = filter.trim().toLowerCase();
  const visible = (items || []).filter((item) => !needle || item.name.toLowerCase().includes(needle));

  return (
    <Box sx={{ opacity: disabled ? 0.6 : 1, pointerEvents: disabled ? "none" : undefined }}>
      <Box sx={{ display: "flex", gap: 1.25, alignItems: "center", flexWrap: "wrap", mb: 1.75 }}>
        <Box sx={{ width: 220 }}>
          <Segmented
            value={ownership}
            onChange={(id) => setOwnership(id as "private" | "public")}
            options={[
              { id: "private", label: "My avatars" },
              { id: "public", label: "Stock" },
            ]}
          />
        </Box>
        <TextField
          size="small"
          placeholder="Filter by name"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          sx={{ flex: "1 1 180px", maxWidth: 280 }}
          slotProps={{ input: { startAdornment: <InputAdornment position="start"><SearchRoundedIcon sx={{ fontSize: 18 }} /></InputAdornment> } }}
        />
        <Tooltip title="Reload from HeyGen">
          <IconButton size="small" onClick={() => void load(ownership, true)} aria-label="Reload avatars">
            <RefreshRoundedIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>
      {error ? <Banner severity="error">{error}</Banner> : null}
      <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(118px, 1fr))", gap: 1.5 }}>
        {ownership === "private" ? (
          <ButtonBase
            onClick={() => setCreating(true)}
            sx={{
              borderRadius: "14px",
              border: `1.5px dashed ${apple.hairlineHover}`,
              bgcolor: apple.hoverFill,
              minHeight: 180,
              display: "flex",
              flexDirection: "column",
              gap: 1,
              color: apple.muted,
              transition: `border-color 0.2s ${apple.smooth}, color 0.2s ${apple.smooth}`,
              "&:hover": { borderColor: mk.main, color: mk.main },
              "&.Mui-focusVisible": { outline: `2px solid ${apple.ink}`, outlineOffset: 2 },
            }}
          >
            <AddAPhotoOutlinedIcon />
            <Typography sx={{ fontSize: 12.5, fontWeight: 600 }}>New from photos</Typography>
          </ButtonBase>
        ) : null}
        {items === null
          ? Array.from({ length: 5 }, (_, index) => <Skeleton key={index} variant="rounded" sx={{ borderRadius: "14px", height: 210 }} />)
          : visible.map((look) => (
              <LookTile
                key={look.id}
                look={look}
                selected={look.id === selectedId}
                onPick={() => onPick(look)}
                onCheck={ownership === "private" ? () => void check(look) : undefined}
                checking={checking === look.id}
              />
            ))}
      </Box>
      {items !== null && !visible.length && !error ? (
        <Typography sx={{ mt: 1.5, fontSize: 13, color: apple.muted }}>
          {needle ? "No avatars match that name." : ownership === "private" ? "No avatars yet. Create one from your photos." : "HeyGen returned no stock avatars."}
        </Typography>
      ) : null}
      {next ? (
        <Box sx={{ mt: 1.5 }}>
          <PillButton variant="gray" size="small" onClick={() => void loadMore()} disabled={more}>
            {more ? "Loading…" : "Load more"}
          </PillButton>
        </Box>
      ) : null}
      <CreateAvatarDialog
        open={creating}
        groups={groups}
        onClose={() => setCreating(false)}
        onCreated={(result) => {
          setCreating(false);
          void load("private", true);
          const first = result.looks.find((look) => look.ready);
          if (first) onPick(first);
        }}
      />
    </Box>
  );
}

type Photo = { file: File; url: string; label: string };

export function CreateAvatarDialog({ open, onClose, groups, onCreated }: { open: boolean; onClose: () => void; groups: { id: string; name: string }[]; onCreated: (result: CreatedAvatar) => void }) {
  const [name, setName] = useState("");
  const [group, setGroup] = useState("");
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const urls = useRef<Set<string>>(new Set());

  useEffect(() => {
    const live = urls.current;
    return () => live.forEach((url) => URL.revokeObjectURL(url));
  }, []);

  const reset = () => {
    photos.forEach((photo) => {
      URL.revokeObjectURL(photo.url);
      urls.current.delete(photo.url);
    });
    setPhotos([]);
    setName("");
    setGroup("");
    setError("");
  };

  const add = (files: File[]) => {
    const images = files.filter((file) => file.type.startsWith("image/"));
    const tooBig = images.filter((file) => file.size > MAX_PHOTO_BYTES);
    const room = MAX_PHOTOS - photos.length;
    const accepted = images.filter((file) => file.size <= MAX_PHOTO_BYTES).slice(0, Math.max(room, 0));
    const problems = [
      images.length < files.length ? "Only image files can become looks." : "",
      tooBig.length ? "Each photo must be under 20 MB." : "",
      images.length - tooBig.length > room ? `Up to ${MAX_PHOTOS} photos at a time.` : "",
    ].filter(Boolean);
    setError(problems.join(" "));
    setPhotos((current) => [
      ...current,
      ...accepted.map((file) => {
        const url = URL.createObjectURL(file);
        urls.current.add(url);
        return { file, url, label: "" };
      }),
    ]);
  };

  const remove = (index: number) => {
    setPhotos((current) => {
      const gone = current[index];
      if (gone) {
        URL.revokeObjectURL(gone.url);
        urls.current.delete(gone.url);
      }
      return current.filter((_, at) => at !== index);
    });
  };

  const existing = groups.find((item) => item.id === group);
  const characterName = existing ? existing.name : name.trim();
  const ready = Boolean(characterName) && photos.length > 0 && !busy;

  const submit = async () => {
    if (!ready) return;
    setBusy(true);
    setError("");
    const form = new FormData();
    form.append("name", characterName);
    form.append("group_id", group);
    photos.forEach((photo) => form.append("look_names", photo.label.trim()));
    photos.forEach((photo) => form.append("photos", photo.file, photo.file.name));
    try {
      const result = await avatarApi.createAvatar(form);
      reset();
      onCreated(result);
    } catch (err) {
      setError(errorText(err, "HeyGen could not create the avatar."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AppDialog
      open={open}
      onClose={() => {
        if (busy) return;
        reset();
        onClose();
      }}
      title="New avatar from photos"
      titleId="create-avatar-title"
      maxWidth="md"
      actions={
        <>
          <PillButton variant="text" onClick={() => { reset(); onClose(); }} disabled={busy}>
            Cancel
          </PillButton>
          <PillButton onClick={() => void submit()} disabled={!ready}>
            {busy
              ? `Uploading ${photos.length} photo${photos.length === 1 ? "" : "s"}…`
              : photos.length
                ? `Create ${photos.length} look${photos.length === 1 ? "" : "s"}`
                : "Create looks"}
          </PillButton>
        </>
      }
    >
      <Typography sx={{ fontSize: 13.5, color: apple.muted, lineHeight: 1.55, mb: 2 }}>
        Each photo becomes one look of the same presenter, and HeyGen charges for every look it creates. New looks train for a few minutes before they can render.
      </Typography>
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: groups.length ? "1fr 1fr" : "1fr" }, gap: 1.5, mb: 2 }}>
        {groups.length ? (
          <TextField select size="small" label="Presenter" value={group} onChange={(event) => setGroup(event.target.value)} disabled={busy}>
            <MenuItem value="">New presenter</MenuItem>
            {groups.map((item) => (
              <MenuItem key={item.id} value={item.id}>
                Add looks to {item.name}
              </MenuItem>
            ))}
          </TextField>
        ) : null}
        {!existing ? (
          <TextField size="small" label="Presenter name" value={name} onChange={(event) => setName(event.target.value.slice(0, 80))} disabled={busy} autoFocus required />
        ) : null}
      </Box>
      <DropZone
        accept="image/jpeg,image/png,image/webp,image/heic"
        multiple
        onFiles={add}
        disabled={busy || photos.length >= MAX_PHOTOS}
        icon={<AddAPhotoOutlinedIcon />}
        title={photos.length >= MAX_PHOTOS ? `${MAX_PHOTOS} photos added` : "Drop photos here or browse"}
        hint="Well-lit, front-facing, one person per photo, at least 1080 px on the short side, face large in frame. Send originals, not WhatsApp copies. Black letterbox bars are trimmed automatically."
      />
      {photos.length ? (
        <Box sx={{ mt: 2, display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(132px, 1fr))", gap: 1.5 }}>
          {photos.map((photo, index) => {
            const primary = !existing && index === 0;
            return (
              <Box key={photo.url} sx={{ borderRadius: "12px", border: `1px solid ${apple.hairline}`, overflow: "hidden", bgcolor: apple.raised }}>
                <Box sx={{ position: "relative", aspectRatio: "3 / 4" }}>
                  <Box component="img" src={photo.url} alt="" sx={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
                  <IconButton size="small" onClick={() => remove(index)} disabled={busy} aria-label="Remove photo" sx={{ position: "absolute", top: 6, right: 6, bgcolor: apple.page, "&:hover": { bgcolor: apple.page } }}>
                    <CloseRoundedIcon sx={{ fontSize: 16 }} />
                  </IconButton>
                </Box>
                <Box sx={{ p: 1 }}>
                  {primary ? (
                    <Typography sx={{ fontSize: 12, color: apple.muted, py: 0.6 }}>Main look · {characterName || "presenter"}</Typography>
                  ) : (
                    <TextField
                      size="small"
                      fullWidth
                      placeholder={`${characterName || "Look"} ${index + 1}`}
                      value={photo.label}
                      disabled={busy}
                      onChange={(event) => {
                        const label = event.target.value.slice(0, 80);
                        setPhotos((current) => current.map((item, at) => (at === index ? { ...item, label } : item)));
                      }}
                      slotProps={{ htmlInput: { "aria-label": `Look name for photo ${index + 1}` } }}
                    />
                  )}
                </Box>
              </Box>
            );
          })}
        </Box>
      ) : null}
      {error ? (
        <Box sx={{ mt: 2 }}>
          <Banner severity="error">{error}</Banner>
        </Box>
      ) : null}
    </AppDialog>
  );
}
