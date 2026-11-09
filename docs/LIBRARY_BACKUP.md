# Library backup archive and manual restore

`GET /api/library/backup` produces a version-2 ZIP of project directories and the ideas shelf. The archive is local to the browser download; it is not uploaded elsewhere.

## What's inside

- Each screenplay project remains at `<project-id>/...` and is listed under `projects` in `library-backup.json`.
- The ideas shelf remains at `ideas/<idea-id>/...` and is listed separately under `ideas`; it is not a screenplay project.
- Lock files and temporary write files are excluded. Unreadable or unsafe-to-follow files are recorded under `skipped`; damaged or unsafe project roots are recorded under `failed`. `complete` is false if either list is non-empty.
- Project manifest API keys are redacted and named under `credentials_withheld`.
- Writer relationship memory (`writer_profile.json`) is **excluded by default** because it can contain personal preferences and observations. The desk asks before download. Choosing to include it makes the archive contain `writer_profile.json`; the embedded `writer_memory` entry records that explicit choice. An archive without this file does not preserve the relationship memory.

## Manual restore

There is **no in-app restore/import route**. The ZIP is a filesystem archive, not an automatically merged restore. To check or restore it safely:

1. Stop the Studio process.
2. Create a **new, empty** projects directory. Do not extract over an existing library; this archive does not resolve collisions or merge concurrent changes.
3. Extract the archive contents into that directory, preserving folders. The embedded `library-backup.json` is a description file; project and idea data stay in their original relative paths.
4. Start the Studio against that directory, for example: `python -m screenplay_studio.webapp_server --projects-dir ./restored_projects`.
5. Check the shelf and ideas pages before treating the restore as complete. Review `failed`, `skipped`, `complete`, and `writer_memory` in `library-backup.json`.

Only restore an archive you created and trust. This is a manual filesystem operation; the Studio does not validate arbitrary ZIP uploads. Do not treat a partial archive (`complete: false`) or an archive with `writer_memory.included: false` as a full copy of all Studio state.
