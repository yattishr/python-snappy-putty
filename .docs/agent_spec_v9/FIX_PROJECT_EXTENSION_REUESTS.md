## Patch: Treat frontend/interface requests as project-extension requests

Problem:
When running Snappy inside a vanilla Node.js REST API project, the user can run `inspect project` successfully, but asking:

`help me build a frontend interface for this application`

returns:

`This request does not appear to be related to the current project.`

This is incorrect. A frontend for an existing backend/API project is a project-extension request.

Current project snapshot includes:
- languages: javascript, json
- package manager: npm
- source files such as server.js, controllers/productControllers.js, models/productModel.js, data/products.json
- no existing frontend files

Expected behavior:
Snappy should classify this as project-related because the user refers to "this application" and asks to build a frontend interface for it.

Implementation requirements:
1. Update the project relevance classifier/check so it supports a new relationship type:
   - `project_extension`

2. Treat requests as project-related when:
   - the request contains phrases like:
     - "for this application"
     - "for this project"
     - "for this app"
     - "build a frontend"
     - "frontend interface"
     - "UI for this"
     - "dashboard for this"
   AND the snapshot indicates a backend/API/server project, such as:
     - `server.js`
     - controllers/
     - routes/
     - api/
     - package.json with npm
     - Express/server-related dependencies where available
     - source files suggesting REST API structure

3. Skill matching should inform the relevance decision:
   - If `frontend-design` matches and the user references the current app/project/application, do not reject as unrelated.
   - The matched skill should be included in planning metadata.
   - The skill must not execute directly or bypass confirmation.

4. If a recent project inspection exists, ensure planning uses the latest snapshot, not a stale snapshot.
   - Add or update tests to verify that after `inspect project`, the next planning request uses the latest saved snapshot.

5. Add regression tests:
   - Given a vanilla Node.js REST API snapshot with server.js and controllers/productControllers.js
   - And a frontend-design skill loaded
   - When the user asks: "help me build a frontend interface for this application"
   - Then Snappy creates a grounded project plan instead of rejecting it as unrelated
   - The plan metadata includes:
     - relationship: project_extension
     - matched skill: frontend-design
   - The plan proposes inspection of API routes before creating frontend files
   - No files are written without confirmation

6. Keep existing protections:
   - Do not weaken unrelated-request rejection generally.
   - Do not let skills bypass rules, confirmation, or execution safety.
   - Do not create files unless the user confirms the plan.

Verification:
- `python -m py_compile src/snappy_putty/*.py`
- `python -m pytest`
