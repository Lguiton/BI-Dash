// The fields you can work in, grouped. Each one opens its own dashboard (/field/<id>); IT repair, Network and Cybersecurity keep their existing track dashboards.
export type FieldItem = {
  id: string; label: string; blurb: string; href: string;
  services: string[];                                      // service-list groups that belong to this field
  match: (path: string) => boolean;
};
export type FieldGroup = { id: string; label: string; items: FieldItem[] };

const own = (id: string, label: string, blurb: string, services: string[]): FieldItem => ({ id, label, blurb, href: `/field/${id}`, services, match: (p) => p === `/field/${id}` });
const track = (id: string, slug: string, label: string, blurb: string, services: string[]): FieldItem => ({ id, label, blurb, href: `/tracks/${slug}?view=tools`, services, match: (p) => p.startsWith(`/tracks/${slug}`) });

export const FIELD_GROUPS: FieldGroup[] = [
  { id: "data", label: "Data", items: [
    own("analyst", "Data Analyst", "Questions to answers: pivots, charts, A/B reads, notebooks, data stories.", ["data"]),
    own("bi", "BI", "Dashboards, KPI dictionaries, scheduled reports, revenue operations.", ["bi"]),
    own("science", "Data Science", "Forecasts, models, segmentation and honest accuracy checks.", ["ds"]),
    own("eng", "Data Engineering", "Pipelines, schemas, quality rules and loading data reliably.", ["data"]),
  ] },
  { id: "tech", label: "Tech", items: [
    track("itsupport", "itsupport", "IT repair", "Helpdesk tickets, repair guides, inventory, backups and your fix log.", ["it"]),
    track("network", "network", "Network", "Subnets, configs, packet captures, design and your fix log.", ["net"]),
    track("security", "security", "Cybersecurity", "Defensive checkups, incident help, hardening and your fix log.", ["sec"]),
    own("cpe", "Computer engineering", "Parts checks, battery life, sketches and test plans for boards and builds.", ["cpe"]),
    own("devsecops", "DevSecOps", "Pipeline and cloud security checks, plus revenue-system security.", ["sec"]),
    own("fs", "Full stack", "Scaffolds, API contracts, code review reports, deploy runbooks, DevOps.", ["fs", "devops"]),
    own("cloud", "Cloud", "Cloud architecture sizing, cost estimates and design write-ups.", ["devops"]),
  ] },
  { id: "ai", label: "AI and Research", items: [
    own("ai", "AI engineering", "Evals, prompt library, cost estimates, risk register and handoff packs.", ["ai"]),
    own("ml", "ML, NLP and DL", "Text classifiers, extraction tests, experiments and computer vision.", ["ds", "ai"]),
    own("health", "Health data", "Clinical data science, health analytics, health BI and informatics. Made-up or de-identified data only.", ["health"]),
    own("research", "Science and research", "Statistics, genomic data science and research methods.", ["stat"]),
  ] },
  { id: "business", label: "Business", items: [
    own("pm", "Project management", "Proposals, status reports, estimates, user stories and IT project plans.", ["pm"]),
    own("consulting", "Business consulting", "Assessments, strategy documents, leadership and process tools.", ["biz"]),
    own("marketing", "Marketing and design", "Digital marketing, social media, UI/UX and graphic design tools.", ["mkt", "ux"]),
  ] },
];

export const ALL_FIELDS: FieldItem[] = FIELD_GROUPS.flatMap((g) => g.items);
export const fieldById = (id: string): FieldItem | undefined => ALL_FIELDS.find((f) => f.id === id);

/** Old links (/toolbox?role=… and /fields?f=…&pack=…) forward to the field's own page. */
export function legacyFieldHref(role: string | null, f: string | null, pack: string | null): string | null {
  const q = pack ? `?pack=${encodeURIComponent(pack)}` : "";
  if (role) {
    if (role === "sec") return `/field/devsecops${q}`;
    if (role === "pm" && pack === "biz") return `/field/consulting`;
    if (fieldById(role) && role !== "howto") return `/field/${role}${q}`;
    return null;
  }
  if (f === "health") return `/field/health${q}`;
  if (f === "science") return `/field/research${q}`;
  if (f === "cloud") return pack === "mkt" || pack === "ux" ? `/field/marketing${q}` : `/field/cloud${q}`;
  return null;
}
