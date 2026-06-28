---
name: portfolio-project-updater
description: Guidelines for adding and formatting new projects in the developer portfolio repository (mock_portfolio).
---

# Portfolio Project Updater Skill

Use this skill when synchronizing a new project into the `mock_portfolio` repository. You must update both the project data array and the visual slide component files by adhering to these exact requirements:

---

## 1. Project Data Insertion & Renumbering

### Target File:
- [`mock_portfolio/app/data/portfolio.ts`](file:///Users/saransh/vs%20code/Developer%20Portfolio%20AutoSync%20Agent/mock_portfolio/app/data/portfolio.ts)

### Array Position & Renumbering Rules:
- Insert the new project object at index 0 (the beginning) of the `projectsData` array.
- **Renumbering**: Set the newly added project's `order` property to `"Project 1"`.
- Shift the `order` label of all pre-existing projects in the array up by one (e.g., previous `"Project 1"` becomes `"Project 2"`, previous `"Project 2"` becomes `"Project 3"`, etc.).

---

## 2. High-Fidelity Project Descriptions

- **Do Not Use Taglines**: Avoid simply copying the raw GitHub repository description or tagline.
- **Professional Summaries**: Compose a compelling, professional 2-3 sentence project summary. Highlight the core problem solved, its main capabilities/workflows, and the primary technologies used. Match the tone and length of the pre-existing descriptions in `portfolio.ts`.

---

## 3. Tech Stack Icon Filtering

- **Primary Tech Only**: Only select 3-5 major languages, databases, or frameworks representing the core tech stack.
- **Allowable Tech Keys**: Ensure the `iconKey` properties strictly use the mapped lowercase keys defined in [`TechIcon.tsx`](file:///Users/saransh/vs%20code/Developer%20Portfolio%20AutoSync%20Agent/mock_portfolio/app/components/TechIcon.tsx) (e.g., `python`, `fastapi`, `javascript`, `docker`, `typescript`, `nodejs`, `openai`, `aws`, `postgresql`, `mysql`, `git`, `gcp`, `anthropic`, `huggingface`, `tensorflow`, `pytorch`).
- **Filter Minor Config Languages**: Do not include markup/scripting/config languages like HTML, CSS, Shell, HCL, or Go Templates to prevent generic white circular letter badges from cluttering the portfolio UI.

---

## 4. Custom SVG Illustration & Visual Theme Injection

Every project must have a custom visual thumbnail. When adding a project, make the following additions to [`mock_portfolio/app/components/ProjectsSection.tsx`](file:///Users/saransh/vs%20code/Developer%20Portfolio%20AutoSync%20Agent/mock_portfolio/app/components/ProjectsSection.tsx):

### A. React SVG Component:
Create a custom React SVG component named `{ClassName}SVG()` representing the project theme (e.g. outline shapes, trend lines, circuits, or shields):
- Use `viewBox="0 0 80 80"`, `width="72"`, `height="72"`, `fill="none"`.
- Use semi-transparent white fills (`rgba(255,255,255,0.15)`) and solid white line strokes (`stroke="rgba(255,255,255,0.5)"` or solid white).
- Place this component definition right before the `PROJECT_SVG` dictionary.

### B. PROJECT_SVG Registry:
Add a key-value entry for your project slug to the `PROJECT_SVG` dictionary mapping to the new component:
```typescript
"my-project-id": <MyNewProjectSVG />,
```

### C. PROJECT_VISUALS Registry:
Add a linear-gradient background matching the project theme to the `PROJECT_VISUALS` dictionary:
```typescript
"my-project-id": { gradient: "linear-gradient(135deg, #color1 0%, #color2 100%)" },
```
