# Running Coursesmith outside Claude Code

Coursesmith assumes the user's local filesystem persists between sessions: the source PDF stays on disk, the `study-guide-{slug}/` folder grows over time, and `manifest.json` carries state forward. Some environments don't offer that. Use this guide for those cases.

## claude.ai

The container is ephemeral and a full book usually won't fit a single chat. Adapt as follows.

**Setup:**

1. Upload the book to a Claude Project so it survives between chats in that project.
2. Work inside the project. `coursesmith-init` builds the folder as normal (in the container's working directory).
3. At the end of each chat, zip the folder to `/mnt/user-data/outputs/`:

   ```bash
   python scripts/package_guide.py \
     --source {output_dir} \
     --output /mnt/user-data/outputs/{slug}.zip
   ```

4. Present the zip with `present_files` and tell the user to keep it - it's the only persistent copy of progress.

**Resuming:**

1. Next chat in the same project, the user re-uploads the most recent zip.
2. Unzip it back into the container's working directory:

   ```bash
   unzip {slug}.zip -d .
   ```

3. Read `{slug}/manifest.json` to find the next pending chapter.
4. Invoke `coursesmith-generate` as normal. At the end of the session, zip again and present.

Each session adds one or more chapters; the zip handover is the only difference from Claude Code.

## Cowork

Cowork persists files within a session and can work against a local folder, putting it between Claude Code and claude.ai. Confirm with the user whether the folder genuinely persists between sessions:

- **Persistent folder:** treat exactly like Claude Code. No zipping, no handover.
- **Ephemeral folder:** fall back to the claude.ai approach above (zip at end of session, user re-uploads next time).

## What stays the same

The manifest format, the chapter folder layout, the per-chapter generation flow, the four core principles - none of this changes across environments. Only the read-the-source and deliver-the-output mechanics differ.
