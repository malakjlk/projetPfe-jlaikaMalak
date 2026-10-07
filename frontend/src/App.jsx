import { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import {
  Upload, Activity, Gauge, Workflow, FileCode2, Folder, ChevronRight,
  ChevronLeft, Check, X, Copy, ShieldCheck, FlaskConical, Scale, Search,
  DraftingCompass, Code2, TestTube2, GitCompare, AlertTriangle, Ban, Clock,
  Layers, FolderArchive, Loader2, Circle, Lock, RotateCcw,
} from "lucide-react";

const API_URL = "http://localhost:8000";

/* ────────────────────────────────────────────────
   TOKENS
   Couleurs officielles : PHP #777BB4 · Python #3776AB / #FFD43B
──────────────────────────────────────────────── */
const T = {
  bg: "#F6F7F9", surface: "#FFFFFF", ink: "#0F1B2D", muted: "#5B6B7F",
  faint: "#8A97A8", line: "#E3E8EF",
  php: "#777BB4", phpInk: "#4B4E8C", py: "#3776AB", pyInk: "#24567F",
  jaune: "#FFD43B",
  nuit: "#1B2438", nuit2: "#252F47", nuitLigne: "#33405C",
  ok: "#1E8E5A", okBg: "#EAF6F0", warn: "#C77E1E", warnBg: "#FBF3E4",
  err: "#C24141", errBg: "#FBEDED",
  codeBg: "#0E1116", codeInk: "#D7DEE8",
  radius: 12,
  shadow: "0 1px 2px rgba(15,27,45,.05), 0 8px 24px rgba(15,27,45,.06)",
};
const font = {
  display: "'Sora', system-ui, sans-serif",
  body: "'Inter', system-ui, sans-serif",
  mono: "'JetBrains Mono', ui-monospace, monospace",
};

/* Les agents du système. Le Manager n'exécute rien : il décide qui
   intervient. Les vérifications et la décision sont déterministes. */
const AGENTS = {
  "Manager": { Icone: Layers, role: "Choisit quel agent intervient, à partir de l'état partagé du module", nature: "LLM" },
  "Analyste": { Icone: Search, role: "Tree-sitter : fonctions, classes, failles CWE, invariants de sécurité", nature: "déterministe" },
  "Architecte": { Icone: DraftingCompass, role: "Découpage en modules, stratégie de migration, révision du plan", nature: "déterministe" },
  "Développeur": { Icone: Code2, role: "Génère le Python à partir d'exemples retrouvés par le RAG", nature: "LLM" },
  "Testeur": { Icone: TestTube2, role: "Syntaxe, invariants présents, failles d'origine corrigées", nature: "déterministe" },
  "Comparateur": { Icone: GitCompare, role: "Exécute le PHP et le Python sur les mêmes entrées, base simulée comprise", nature: "déterministe" },
  "Vérificateur de propriétés": { Icone: FlaskConical, role: "Exécution symbolique (Z3) : invariants, injection SQL, contrôle d'accès", nature: "déterministe" },
  "Auditeur": { Icone: ShieldCheck, role: "Bandit, pip-audit, protections d'origine conservées", nature: "déterministe" },
  "Réviseur": { Icone: Scale, role: "Score de confiance à 4 critères : livrer, corriger ou escalader", nature: "déterministe" },
};

const LIBELLE_CRITERE = {
  fonctionnel: "Fonctionnel", securite: "Sécurité",
  comportemental: "Comportemental", proprietes: "Propriétés",
};
const couleurScore = (s) => (s >= 80 ? T.ok : s >= 60 ? T.warn : T.err);

const TON_VERDICT = {
  LIVRER: { fond: T.okBg, encre: T.ok, texte: "Livré" },
  ITERER: { fond: T.warnBg, encre: T.warn, texte: "Correction demandée" },
  REANALYSE_COMPLETE: { fond: T.warnBg, encre: T.warn, texte: "Ré-analyse" },
  REPLANIFIER: { fond: T.warnBg, encre: T.warn, texte: "Plan à réviser" },
  VALIDATION_HUMAINE: { fond: T.warnBg, encre: T.warn, texte: "Validation humaine" },
  ARRET_ECHEC: { fond: T.errBg, encre: T.err, texte: "Échec" },
};
const TON_ISSUE = {
  execute: { ton: "ok", texte: "exécuté" },
  cache: { ton: "neutre", texte: "réutilisé (cache)" },
  deja_fait: { ton: "neutre", texte: "déjà fait" },
  refus_prerequis: { ton: "warn", texte: "refusé, prérequis" },
  indisponible: { ton: "err", texte: "indisponible" },
};
const STATUT_FICHIER = {
  en_attente: { texte: "En attente", couleur: T.faint, Icone: Circle },
  en_cours: { texte: "En cours", couleur: T.py, Icone: Loader2 },
  livre: { texte: "Livré", couleur: T.ok, Icone: Check },
  partiel: { texte: "Partiel", couleur: T.warn, Icone: AlertTriangle },
};

const tailleLisible = (o) => (o > 1048576 ? `${(o / 1048576).toFixed(1)} Mo`
  : `${Math.max(1, Math.round(o / 1024))} Ko`);
const versPy = (nom) => (nom || "").replace(/\.php$/i, ".py");
const nomCourt = (chemin) => (chemin || "").split(/[\\/]/).pop();

/* ────────────────────────────────────────────────
   BRIQUES
──────────────────────────────────────────────── */
function Carte({ children, style }) {
  return (
    <div style={{
      background: T.surface, border: `1px solid ${T.line}`, borderRadius: T.radius,
      boxShadow: T.shadow, minWidth: 0, boxSizing: "border-box", ...style,
    }}>{children}</div>
  );
}
function Etiquette({ children, ton = "neutre" }) {
  const tons = { neutre: [T.bg, T.muted], ok: [T.okBg, T.ok], warn: [T.warnBg, T.warn], err: [T.errBg, T.err] };
  const [fond, encre] = tons[ton] || tons.neutre;
  return (
    <span style={{
      background: fond, color: encre, fontSize: 11.5, fontWeight: 500,
      padding: "3px 8px", borderRadius: 6, whiteSpace: "nowrap",
      display: "inline-flex", alignItems: "center", gap: 4,
    }}>{children}</span>
  );
}
function Titre({ children, apres, niveau = 2 }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14, gap: 10 }}>
      <h2 style={{
        fontFamily: font.display, fontSize: niveau === 1 ? 20 : 15, fontWeight: 600,
        color: T.ink, margin: 0, letterSpacing: "-.01em",
      }}>{children}</h2>
      {apres}
    </div>
  );
}
function Vide({ Icone = Activity, titre, texte, action }) {
  return (
    <Carte style={{ padding: 48, textAlign: "center" }}>
      <Icone size={24} color={T.faint} />
      <div style={{ marginTop: 12, fontSize: 15, color: T.ink, fontWeight: 500 }}>{titre}</div>
      {texte && <div style={{ marginTop: 6, fontSize: 13, color: T.muted }}>{texte}</div>}
      {action && <div style={{ marginTop: 18 }}>{action}</div>}
    </Carte>
  );
}
function Bouton({ children, onClick, desactive, secondaire, Icone }) {
  return (
    <button onClick={onClick} disabled={desactive} style={{
      display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8,
      padding: "10px 16px", borderRadius: 9, fontFamily: font.body, fontSize: 14,
      fontWeight: 600, cursor: desactive ? "default" : "pointer",
      border: secondaire ? `1px solid ${T.line}` : "none",
      background: desactive ? T.line : secondaire ? T.surface : T.py,
      color: desactive ? T.faint : secondaire ? T.ink : "#fff",
    }}>
      {Icone && <Icone size={15} />}{children}
    </button>
  );
}

/* Logo provisoire : à remplacer par le logo définitif. */
function Logo({ taille = 34 }) {
  return (
    <svg width={taille} height={taille} viewBox="0 0 36 36" aria-hidden="true">
      <rect width="36" height="36" rx="9" fill={T.nuit2} stroke={T.nuitLigne} />
      <path d="M15 11 L8 18 L15 25" fill="none" stroke={T.php} strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M21 11 L28 18 L21 25" fill="none" stroke={T.py} strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="18" cy="18" r="2.4" fill={T.jaune} />
    </svg>
  );
}

/* ────────────────────────────────────────────────
   BARRE DU HAUT — le pont PHP → Python porte l'avancement
──────────────────────────────────────────────── */
function problemesEnvironnement(sante) {
  if (!sante) return ["serveur injoignable"];
  const p = [];
  if (!sante.php) p.push("PHP absent");
  if (!sante.pdo_sqlite) p.push("pdo_sqlite absent");
  if (!sante.crosshair) p.push("CrossHair absent");
  if (!sante.cle_groq) p.push("clé Groq absente");
  return p;
}

function EtatEnvironnement({ sante }) {
  const problemes = problemesEnvironnement(sante);
  const ok = problemes.length === 0;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "#D6DCE6" }}>
      <span style={{
        width: 8, height: 8, borderRadius: "50%", background: ok ? "#3BC48A" : "#E26D6D",
        boxShadow: `0 0 0 3px ${ok ? "rgba(59,196,138,.2)" : "rgba(226,109,109,.2)"}`,
      }} />
      {ok ? "Environnement prêt" : problemes[0]}
    </div>
  );
}

function BarreHaute({ sante, tache, resultat }) {
  const direct = tache?.en_direct;
  const enCours = tache?.statut === "en_cours";
  const etapes = Object.values(direct?.etapes || {});
  const etapesFaites = etapes.filter(Boolean).length;

  let source = null, cible = null, progression = 0;
  if (enCours && direct?.fichier_courant) {
    source = direct.fichier_courant;
    cible = versPy(source);
    progression = etapes.length ? Math.max(0.04, etapesFaites / etapes.length) : 0.04;
  } else if (resultat?.rapport?.fichiers_migres?.length) {
    // migration terminée : on résume le projet entier
    const fichiers = resultat.rapport.fichiers_migres;
    const livres = fichiers.filter((f) => f.statut === "livré").length;
    source = tache?.libelle || nomCourt(fichiers[0].source);
    cible = `${livres} fichier${livres > 1 ? "s" : ""} livré${livres > 1 ? "s" : ""} sur ${fichiers.length}`;
    progression = 1;
  }
  const dernierAgent = direct?.journal?.at(-1)?.agent;

  return (
    <header style={{
      background: T.nuit, height: 68, padding: "0 28px", display: "flex",
      alignItems: "center", justifyContent: "space-between", gap: 20,
      position: "sticky", top: 0, zIndex: 10,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 250 }}>
        <Logo />
        <div>
          <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 15, color: "#F4F6FA", letterSpacing: "-.01em" }}>
            Migration PHP → Python
          </div>
          <div style={{ fontSize: 12, color: "#9AA8BC" }}>Système multi-agents</div>
        </div>
      </div>

      {source ? (
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 11.5, color: "#B3B5E4" }}>Code d'origine</div>
            <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 15, color: "#F4F6FA" }}>{source}</div>
          </div>
          <div style={{ position: "relative", width: 200, height: 3, borderRadius: 2, background: T.nuitLigne }}>
            <div style={{
              position: "absolute", left: 0, top: 0, bottom: 0, width: `${progression * 100}%`, borderRadius: 2,
              background: `linear-gradient(90deg, ${T.php}, ${T.py})`, transition: "width .6s ease",
            }} />
            <div style={{
              position: "absolute", left: `${progression * 100}%`, top: "50%",
              transform: "translate(-50%,-50%)", width: 12, height: 12, borderRadius: "50%",
              background: T.jaune, boxShadow: "0 0 0 4px rgba(255,212,59,.2)", transition: "left .6s ease",
            }} />
          </div>
          <div>
            <div style={{ fontSize: 11.5, color: "#8DBBE3" }}>Code migré</div>
            <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 15, color: "#F4F6FA" }}>{cible}</div>
          </div>
        </div>
      ) : (
        <div style={{ fontSize: 13, color: "#9AA8BC" }}>Aucune migration en cours</div>
      )}

      <div style={{ minWidth: 250, display: "flex", justifyContent: "flex-end" }}>
        {enCours && direct?.module ? (
          <div style={{
            display: "flex", alignItems: "center", gap: 10, background: T.nuit2,
            border: `1px solid ${T.nuitLigne}`, borderRadius: 9, padding: "7px 12px",
          }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: T.jaune, boxShadow: "0 0 0 4px rgba(255,212,59,.19)" }} />
            <div>
              <div style={{ fontFamily: font.display, fontWeight: 600, fontSize: 13, color: "#F4F6FA" }}>{direct.module}</div>
              <div style={{ fontSize: 12, color: "#9AA8BC" }}>
                {dernierAgent ? `${dernierAgent}, ` : ""}étape {etapesFaites} sur {etapes.length || 8}
              </div>
            </div>
          </div>
        ) : <EtatEnvironnement sante={sante} />}
      </div>
    </header>
  );
}

/* ────────────────────────────────────────────────
   BARRE LATÉRALE
──────────────────────────────────────────────── */
const VUES = [
  { id: "nouvelle", titre: "Nouvelle migration", Icone: Upload },
  { id: "suivi", titre: "Suivi en direct", Icone: Activity },
  { id: "resultats", titre: "Résultats", Icone: Gauge },
  { id: "architecture", titre: "Architecture", Icone: Workflow },
];

function BarreLaterale({ vue, setVue, enCours, sante }) {
  return (
    <aside style={{
      width: 232, flexShrink: 0, background: T.surface, borderRight: `1px solid ${T.line}`,
      padding: "18px 12px", display: "flex", flexDirection: "column", gap: 4,
      position: "sticky", top: 68, height: "calc(100vh - 68px)", boxSizing: "border-box",
    }}>
      {VUES.map(({ id, titre, Icone }) => {
        const actif = vue === id;
        return (
          <button key={id} onClick={() => setVue(id)} style={{
            display: "flex", alignItems: "center", gap: 11, width: "100%",
            padding: "10px 12px", borderRadius: 9, border: "none", cursor: "pointer",
            background: actif ? "#EEF4FA" : "transparent", color: actif ? T.pyInk : T.muted,
            fontFamily: font.body, fontSize: 14, fontWeight: actif ? 600 : 500, textAlign: "left",
          }}>
            <Icone size={17} />
            <span style={{ flex: 1 }}>{titre}</span>
            {id === "suivi" && enCours && (
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: T.jaune, boxShadow: "0 0 0 3px rgba(255,212,59,.3)" }} />
            )}
          </button>
        );
      })}
      <div style={{ marginTop: "auto", padding: "14px 12px 4px", borderTop: `1px solid ${T.line}`, fontSize: 12, color: T.faint, lineHeight: 1.7 }}>
        <div>Génération : <span style={{ color: T.muted }}>{sante?.modele_generation || "—"}</span></div>
        <div>Mode : <span style={{ color: T.muted }}>{sante?.mode === "orchestre" ? "orchestré" : "direct"}</span></div>
        {sante?.mode === "orchestre" && (
          <div>Orchestrateur : <span style={{ color: T.muted }}>{sante?.orchestrateur || "—"}</span></div>
        )}
      </div>
    </aside>
  );
}

/* ────────────────────────────────────────────────
   VUE 1 — NOUVELLE MIGRATION
──────────────────────────────────────────────── */
function VueNouvelle({ onLance, occupe, sante }) {
  const [fichier, setFichier] = useState(null);
  const [survol, setSurvol] = useState(false);
  const champ = useRef(null);
  const estZip = fichier?.name.toLowerCase().endsWith(".zip");

  const verifs = [
    ["PHP", sante?.php ? sante.php.replace(/^PHP\s*/i, "").split(" (")[0] : null, "exécute le code d'origine pour la comparaison"],
    ["pdo_sqlite", sante?.pdo_sqlite, "base simulée pour les fonctions à base de données"],
    ["CrossHair", sante?.crosshair, "exécution symbolique du Vérificateur de propriétés"],
    ["Clé Groq", sante?.cle_groq, "génération du code"],
    ["Clé Gemini", sante?.cle_gemini, "orchestration en mode orchestré"],
  ];

  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.4fr) minmax(0,1fr)", gap: 18, alignItems: "start" }}>
      <Carte style={{ padding: 26 }}>
        <Titre niveau={1}>Nouvelle migration</Titre>
        <p style={{ margin: "0 0 18px", fontSize: 13.5, color: T.muted }}>
          Dépose une application PHP complète (.zip) ou un fichier .php seul.
        </p>
        <div
          onDragOver={(e) => { e.preventDefault(); setSurvol(true); }}
          onDragLeave={() => setSurvol(false)}
          onDrop={(e) => { e.preventDefault(); setSurvol(false); setFichier(e.dataTransfer.files?.[0] || null); }}
          onClick={() => champ.current?.click()}
          style={{
            border: `1.5px dashed ${survol ? T.py : "#CBD5E1"}`, background: survol ? "#F0F6FB" : "#FAFBFC",
            borderRadius: 12, padding: "40px 20px", textAlign: "center", cursor: "pointer", transition: "all .2s",
          }}>
          <input ref={champ} type="file" accept=".zip,.php" hidden onChange={(e) => setFichier(e.target.files?.[0] || null)} />
          <div style={{ width: 46, height: 46, borderRadius: 12, background: "#EEF4FA", display: "grid", placeItems: "center", margin: "0 auto" }}>
            <Upload size={20} color={T.py} />
          </div>
          <div style={{ marginTop: 12, fontSize: 14.5, color: T.ink, fontWeight: 500 }}>Glisse ton fichier ici, ou clique pour parcourir</div>
          <div style={{ marginTop: 4, fontSize: 12.5, color: T.faint }}>Formats acceptés : .zip, .php</div>
        </div>

        {fichier && (
          <div style={{ marginTop: 14, display: "flex", alignItems: "center", gap: 12, padding: "12px 14px", border: `1px solid ${T.line}`, borderRadius: 10 }}>
            <div style={{ width: 36, height: 36, borderRadius: 9, background: estZip ? "#EEF4FA" : "#F0F0F8", display: "grid", placeItems: "center" }}>
              {estZip ? <FolderArchive size={17} color={T.py} /> : <FileCode2 size={17} color={T.php} />}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13.5, color: T.ink, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{fichier.name}</div>
              <div style={{ fontSize: 12, color: T.faint }}>{estZip ? "Application complète" : "Fichier seul"}, {tailleLisible(fichier.size)}</div>
            </div>
            <button onClick={() => setFichier(null)} style={{ background: "none", border: "none", cursor: "pointer", color: T.faint }}>
              <X size={16} />
            </button>
          </div>
        )}

        <div style={{ marginTop: 18, display: "flex", justifyContent: "flex-end" }}>
          <Bouton desactive={!fichier || occupe} onClick={() => onLance(fichier)} Icone={ChevronRight}>
            {occupe ? "Une migration est déjà en cours" : "Lancer la migration"}
          </Bouton>
        </div>
      </Carte>

      <Carte style={{ padding: 22 }}>
        <Titre>Environnement</Titre>
        <div style={{ display: "grid", gap: 12 }}>
          {verifs.map(([nom, ok, role]) => (
            <div key={nom} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
              <div style={{ width: 20, height: 20, borderRadius: "50%", flexShrink: 0, display: "grid", placeItems: "center", background: ok ? T.okBg : T.errBg, marginTop: 1 }}>
                {ok ? <Check size={12} color={T.ok} /> : <X size={12} color={T.err} />}
              </div>
              <div>
                <div style={{ fontSize: 13.5, color: T.ink, fontWeight: 500 }}>
                  {nom}{typeof ok === "string" && <span style={{ color: T.faint, fontWeight: 400 }}> {ok}</span>}
                </div>
                <div style={{ fontSize: 12, color: T.faint }}>{role}</div>
              </div>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 16, paddingTop: 14, borderTop: `1px solid ${T.line}`, fontSize: 12.5, color: T.muted, lineHeight: 1.6 }}>
          Mode <strong style={{ color: T.ink }}>{sante?.mode === "orchestre" ? "orchestré" : "direct"}</strong>
          {sante?.mode === "orchestre" ? " : le Manager choisit l'ordre des agents à chaque étape." : " : les agents s'enchaînent sans Manager."}
          {sante?.mode === "orchestre" && sante?.bascule_autorisee && " Repli automatique sur l'autre fournisseur activé."}
        </div>
      </Carte>
    </div>
  );
}

/* ────────────────────────────────────────────────
   JOURNAL DU MANAGER
──────────────────────────────────────────────── */
function Journal({ journal, enCours }) {
  const [ouvert, setOuvert] = useState(null);
  if (!journal?.length) {
    return <div style={{ color: T.faint, fontSize: 13, padding: "12px 0" }}>
      {enCours ? "En attente de la première sollicitation…" : "Aucune sollicitation enregistrée (mode direct)."}
    </div>;
  }
  return (
    <div style={{ position: "relative" }}>
      <div style={{ position: "absolute", left: 15, top: 10, bottom: 10, width: 1, background: T.line }} />
      {journal.map((e, i) => {
        const agent = AGENTS[e.agent] || {};
        const Icone = agent.Icone || Activity;
        const issue = TON_ISSUE[e.issue] || { ton: "neutre", texte: e.issue };
        const estOuvert = ouvert === i;
        const bord = issue.ton === "err" ? T.err : issue.ton === "warn" ? T.warn : T.line;
        return (
          <div key={i} style={{ position: "relative", paddingLeft: 44, paddingBottom: 14, minWidth: 0 }}>
            <div style={{
              position: "absolute", left: 3, top: 1, width: 26, height: 26, borderRadius: "50%",
              background: T.surface, border: `1px solid ${bord}`, display: "grid", placeItems: "center",
            }}><Icone size={13} color={issue.ton === "warn" ? T.warn : T.pyInk} /></div>
            <button onClick={() => setOuvert(estOuvert ? null : i)} style={{
              width: "100%", textAlign: "left", background: "none", border: "none", padding: 0,
              cursor: "pointer", font: "inherit", color: "inherit", display: "block", minWidth: 0,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <span style={{ fontSize: 11.5, color: T.faint, fontFamily: font.mono }}>{String(i + 1).padStart(2, "0")}</span>
                <span style={{ fontWeight: 600, fontSize: 14, color: T.ink }}>{e.agent}</span>
                <Etiquette ton={issue.ton}>{issue.texte}</Etiquette>
                {e.iteration > 1 && <Etiquette>itération {e.iteration}</Etiquette>}
                <ChevronRight size={14} color={T.faint} style={{ marginLeft: "auto", transform: estOuvert ? "rotate(90deg)" : "none", transition: "transform .2s" }} />
              </div>
              {e.justification_manager && (
                <div style={{ fontSize: 13, color: T.muted, marginTop: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: estOuvert ? "normal" : "nowrap" }}>
                  {e.justification_manager}
                </div>
              )}
            </button>
            {estOuvert && (
              <div style={{ marginTop: 8, padding: 12, background: T.bg, borderRadius: 8, fontSize: 12.5, color: T.muted, border: `1px solid ${T.line}` }}>
                <div><strong style={{ color: T.ink }}>Rôle.</strong> {agent.role || "—"}</div>
                {e.etapes_restantes_avant?.length > 0 && (
                  <div style={{ marginTop: 4 }}><strong style={{ color: T.ink }}>Restait à faire.</strong> {e.etapes_restantes_avant.join(", ").replace(/_/g, " ")}</div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ────────────────────────────────────────────────
   VUE 2 — SUIVI EN DIRECT
──────────────────────────────────────────────── */
function ListeFichiers({ fichiers, statuts, courant }) {
  if (!fichiers?.length) return <div style={{ fontSize: 13, color: T.faint }}>Préparation de l'analyse du projet…</div>;
  return (
    <div style={{ display: "grid", gap: 4 }}>
      {fichiers.map((f) => {
        const st = STATUT_FICHIER[statuts?.[f]] || STATUT_FICHIER.en_attente;
        const estCourant = f === courant;
        return (
          <div key={f} style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 10px", borderRadius: 9, background: estCourant ? "#EEF4FA" : "transparent" }}>
            <FileCode2 size={15} color={T.php} />
            <span style={{ flex: 1, fontSize: 13.5, color: T.ink, fontWeight: estCourant ? 600 : 400 }}>{f}</span>
            <span style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12, color: st.couleur }}>
              <st.Icone size={13} style={st.Icone === Loader2 ? { animation: "tourne 1.2s linear infinite" } : undefined} />
              {st.texte}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function VueSuivi({ tache, resultat, allerA }) {
  const direct = tache?.en_direct;
  const enCours = tache?.statut === "en_cours";

  if (!tache) {
    return <Vide Icone={Activity} titre="Aucune migration lancée" texte="Le suivi s'affiche ici dès qu'une migration démarre."
      action={<Bouton onClick={() => allerA("nouvelle")} Icone={Upload}>Nouvelle migration</Bouton>} />;
  }

  const rapport = resultat?.rapport;
  const fichiersRapport = rapport?.fichiers_migres || [];
  const fichiers = enCours ? direct?.fichiers : fichiersRapport.map((f) => nomCourt(f.source));
  const statuts = enCours ? direct?.statuts_fichiers
    : Object.fromEntries(fichiersRapport.map((f) => [nomCourt(f.source), f.statut === "livré" ? "livre" : "partiel"]));
  const modulesFinis = enCours ? (direct?.modules_termines || [])
    : fichiersRapport.flatMap((f) => (f.modules || []).map((m) => ({ module: m.nom_python, decision: m.decision_finale, score: m.score_final })));

  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0,300px) minmax(0,1fr)", gap: 18, alignItems: "start" }}>
      <div style={{ display: "grid", gap: 18, minWidth: 0 }}>
        <Carte style={{ padding: 18 }}>
          <Titre apres={enCours ? <Etiquette ton="warn"><Clock size={11} /> en cours</Etiquette>
            : tache.statut === "termine" ? <Etiquette ton="ok">terminé</Etiquette> : <Etiquette ton="err">échec</Etiquette>}>
            Fichiers
          </Titre>
          <ListeFichiers fichiers={fichiers} statuts={statuts} courant={enCours ? direct?.fichier_courant : null} />
        </Carte>
        <Carte style={{ padding: 18 }}>
          <Titre>Modules terminés</Titre>
          {modulesFinis.length === 0 ? <div style={{ fontSize: 13, color: T.faint }}>Aucun pour l'instant.</div> : (
            <div style={{ display: "grid", gap: 8 }}>
              {modulesFinis.map((m, i) => {
                const ton = TON_VERDICT[m.decision] || TON_VERDICT.ITERER;
                return (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: ton.encre }} />
                    <span style={{ flex: 1, color: T.ink, fontFamily: font.mono, fontSize: 12.5 }}>{m.module}</span>
                    <span style={{ color: ton.encre, fontSize: 12 }}>{(m.score ?? 0).toFixed(0)}%</span>
                  </div>
                );
              })}
            </div>
          )}
        </Carte>
      </div>

      <div style={{ display: "grid", gap: 18, minWidth: 0 }}>
        {enCours && (
          <Carte style={{ padding: 20 }}>
            <Titre apres={direct?.module && <span style={{ fontFamily: font.mono, fontSize: 13, color: T.pyInk }}>{direct.module}</span>}>Module en cours</Titre>
            <div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}>
              {Object.entries(direct?.etapes || {}).map(([nom, fait]) => (
                <Etiquette key={nom} ton={fait ? "ok" : "neutre"}>{fait ? <Check size={11} /> : <Circle size={9} />} {nom.replace(/_/g, " ")}</Etiquette>
              ))}
            </div>
            {direct?.points_attention?.length > 0 && (
              <div style={{ marginTop: 14, display: "grid", gap: 7 }}>
                {direct.points_attention.slice(0, 5).map((p, i) => (
                  <div key={i} style={{ fontSize: 13, color: T.muted, display: "flex", gap: 8 }}>
                    <AlertTriangle size={14} color={T.warn} style={{ flexShrink: 0, marginTop: 2 }} /><span>{p}</span>
                  </div>
                ))}
              </div>
            )}
          </Carte>
        )}

        {tache.statut === "echec" && (
          <Carte style={{ padding: 18, background: T.errBg, borderColor: "#E9B8B8" }}>
            <div style={{ color: T.err, fontWeight: 600, marginBottom: 6 }}>La migration a échoué</div>
            <pre style={{ margin: 0, fontSize: 12, color: T.err, whiteSpace: "pre-wrap", fontFamily: font.mono }}>{String(tache.erreur || "").slice(0, 600)}</pre>
          </Carte>
        )}

        <Carte style={{ padding: 20 }}>
          <Titre apres={<span style={{ fontSize: 12.5, color: T.faint }}>ordre choisi par le Manager, pas une séquence fixe</span>}>Journal du Manager</Titre>
          {enCours ? <Journal journal={direct?.journal} enCours /> : tache.statut === "termine" && (
            <div style={{ fontSize: 13, color: T.muted }}>
              Migration terminée. Le journal de chaque module est dans{" "}
              <button onClick={() => allerA("resultats")} style={{ background: "none", border: "none", color: T.py, cursor: "pointer", padding: 0, font: "inherit", fontWeight: 600 }}>Résultats</button>.
            </div>
          )}
        </Carte>
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────
   VUE 3 — RÉSULTATS
──────────────────────────────────────────────── */
function Confiance({ confiance, score, verdict }) {
  const ton = TON_VERDICT[verdict] || TON_VERDICT.ITERER;
  const niveau = { elevee: "élevée", moyenne: "moyenne", faible: "faible" };
  return (
    <Carte style={{ padding: 22 }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 28 }}>
        <div style={{ minWidth: 150 }}>
          <div style={{ fontSize: 11.5, color: T.faint, textTransform: "uppercase", letterSpacing: ".08em", fontWeight: 500 }}>Score de confiance</div>
          <div style={{ fontFamily: font.display, fontSize: 42, fontWeight: 600, color: couleurScore(score || 0), lineHeight: 1.1, marginTop: 4 }}>
            {(score ?? 0).toFixed(1)}<span style={{ fontSize: 21 }}>%</span>
          </div>
          <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
            <span style={{ background: ton.fond, color: ton.encre, fontSize: 12, fontWeight: 600, padding: "4px 10px", borderRadius: 6 }}>{ton.texte}</span>
            {confiance && <Etiquette>confiance {niveau[confiance.niveau] || confiance.niveau}</Etiquette>}
          </div>
        </div>
        <div style={{ flex: 1, display: "grid", gap: 12 }}>
          {(confiance?.criteres || []).map((c) => (
            <div key={c.nom}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 5 }}>
                <span style={{ color: c.mesure ? T.ink : T.faint, fontWeight: 500 }}>
                  {LIBELLE_CRITERE[c.nom] || c.nom}<span style={{ color: T.faint, fontWeight: 400 }}>, {c.agent}</span>
                </span>
                <span style={{ fontSize: 12.5, color: c.mesure ? couleurScore(c.score) : T.faint, fontWeight: 500 }}>
                  {c.mesure ? `${c.score.toFixed(0)}%, poids ${(c.poids * 100).toFixed(0)}%` : "non mesuré"}
                </span>
              </div>
              <div style={{ height: 6, background: T.bg, borderRadius: 3, overflow: "hidden", border: `1px solid ${T.line}` }}>
                {c.mesure && <div style={{ width: `${Math.max(0, Math.min(100, c.score))}%`, height: "100%", background: couleurScore(c.score), transition: "width .5s ease" }} />}
              </div>
              {!c.mesure && c.raison && <div style={{ fontSize: 12, color: T.faint, marginTop: 4 }}>{c.raison} ; son poids est redistribué.</div>}
            </div>
          ))}
          {!confiance && <div style={{ fontSize: 13, color: T.faint }}>Détail des critères indisponible pour ce module.</div>}
        </div>
      </div>
    </Carte>
  );
}

function Preuves({ module }) {
  const [onglet, setOnglet] = useState("comportement");
  const eq = module?.equivalence || {};
  const formel = module?.verification_formelle || {};
  const etat = module?.etat_structure || {};
  const onglets = [
    { id: "comportement", titre: "Comportement", Icone: GitCompare },
    { id: "proprietes", titre: "Propriétés", Icone: FlaskConical },
    { id: "attention", titre: "Points d'attention", Icone: AlertTriangle },
    { id: "journal", titre: "Journal", Icone: Layers },
  ];
  return (
    <Carte style={{ padding: 0, overflow: "hidden" }}>
      <div style={{ display: "flex", borderBottom: `1px solid ${T.line}` }}>
        {onglets.map(({ id, titre, Icone }) => (
          <button key={id} onClick={() => setOnglet(id)} style={{
            flex: 1, padding: "12px 10px", background: onglet === id ? T.surface : T.bg, border: "none",
            borderBottom: onglet === id ? `2px solid ${T.py}` : "2px solid transparent", cursor: "pointer",
            fontFamily: font.body, fontSize: 13, color: onglet === id ? T.ink : T.muted,
            fontWeight: onglet === id ? 600 : 500, display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
          }}><Icone size={14} /> {titre}</button>
        ))}
      </div>
      <div style={{ padding: 20, fontSize: 13.5 }}>
        {onglet === "comportement" && (eq.statut === "teste" ? (
          <div style={{ display: "grid", gap: 12 }}>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <Etiquette ton={eq.score_equivalence >= 0.9 ? "ok" : "warn"}>{((eq.score_equivalence || 0) * 100).toFixed(0)}% d'équivalence</Etiquette>
              <Etiquette>{eq.cas_testes} cas exécutés</Etiquette>
              {eq.base_simulee && <Etiquette>base simulée : {(eq.base_simulee.tables || []).join(", ")}</Etiquette>}
            </div>
            {eq.injections_bloquees?.length > 0 && (
              <div style={{ background: T.okBg, border: "1px solid #BFE3CF", borderRadius: 9, padding: 14 }}>
                <div style={{ color: T.ok, fontWeight: 600, marginBottom: 6, display: "flex", alignItems: "center", gap: 6 }}>
                  <Ban size={15} /> {eq.injections_bloquees.length} injection(s) neutralisée(s)
                </div>
                <div style={{ color: T.muted, fontSize: 13, marginBottom: 8 }}>
                  Le PHP d'origine accepte ces entrées, le Python les bloque. L'écart est volontaire : la faille est corrigée, ce n'est pas une régression.
                </div>
                {eq.injections_bloquees.map((v, i) => (
                  <div key={i} style={{ fontFamily: font.mono, fontSize: 12, color: T.ink, background: T.surface, padding: "5px 9px", borderRadius: 6, marginBottom: 4 }}>{v}</div>
                ))}
              </div>
            )}
            {eq.divergences?.length > 0 ? eq.divergences.slice(0, 6).map((d, i) => (
              <div key={i} style={{ borderLeft: `2px solid ${T.err}`, paddingLeft: 10, fontSize: 13 }}>
                <div style={{ fontFamily: font.mono, fontSize: 12, color: T.faint }}>{d.type}, entrée {JSON.stringify(d.entree)}</div>
                <div style={{ color: T.muted }}>PHP : {JSON.stringify(d.php)?.slice(0, 100)}</div>
                <div style={{ color: T.muted }}>Python : {JSON.stringify(d.python)?.slice(0, 100)}</div>
              </div>
            )) : <div style={{ color: T.ok }}>Aucune divergence : le Python se comporte comme le PHP sur toutes les entrées testées.</div>}
          </div>
        ) : <div style={{ color: T.muted }}>Équivalence non testée{eq.statut ? ` (${eq.statut})` : ""}.{eq.raison && <div style={{ marginTop: 6, color: T.faint }}>{eq.raison}</div>}</div>)}

        {onglet === "proprietes" && (formel.proprietes?.length ? (
          <div style={{ display: "grid", gap: 8 }}>
            <div style={{ color: T.faint, fontSize: 12.5 }}>
              « Prouvée » signifie qu'aucun contre-exemple n'a été trouvé par exploration symbolique dans le budget de temps : une vérification bornée, non une preuve absolue.
            </div>
            {formel.proprietes.map((p, i) => (
              <div key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start", padding: "9px 11px", background: T.bg, borderRadius: 8 }}>
                <Etiquette ton={p.statut === "prouvee" ? "ok" : p.statut === "refutee" ? "err" : "neutre"}>{p.statut}</Etiquette>
                <div style={{ flex: 1 }}>
                  <div style={{ color: T.ink }}>{p.libelle}</div>
                  <div style={{ fontSize: 12, color: T.faint }}>{(p.famille || "").replace(/_/g, " ")}</div>
                  {p.contre_exemple && <div style={{ fontFamily: font.mono, fontSize: 12, color: T.err, marginTop: 4 }}>contre-exemple : {p.contre_exemple}</div>}
                </div>
              </div>
            ))}
          </div>
        ) : <div style={{ color: T.muted }}>Aucune propriété vérifiée sur ce module.</div>)}

        {onglet === "attention" && (etat.points_attention?.length ? (
          <div style={{ display: "grid", gap: 9 }}>
            {etat.points_attention.map((p, i) => (
              <div key={i} style={{ display: "flex", gap: 8, color: T.muted, fontSize: 13 }}>
                <AlertTriangle size={14} color={T.warn} style={{ flexShrink: 0, marginTop: 2 }} /><span>{p}</span>
              </div>
            ))}
          </div>
        ) : <div style={{ color: T.muted }}>Aucun point d'attention signalé.</div>)}

        {onglet === "journal" && <Journal journal={etat.journal} enCours={false} />}
      </div>
    </Carte>
  );
}

function PanneauCode({ titre, contenu, couleur, etiquette }) {
  const [copie, setCopie] = useState(false);
  return (
    <div style={{ minWidth: 0, display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 14px", borderBottom: `1px solid ${T.line}`, background: T.surface }}>
        <span style={{ width: 8, height: 8, borderRadius: 2, background: couleur }} />
        <span style={{ fontSize: 12, color: T.faint }}>{etiquette}</span>
        <span style={{ fontFamily: font.mono, fontSize: 12.5, color: T.ink }}>{titre}</span>
        <button onClick={() => { navigator.clipboard.writeText(contenu || ""); setCopie(true); setTimeout(() => setCopie(false), 1400); }} style={{
          marginLeft: "auto", background: "none", border: `1px solid ${T.line}`, borderRadius: 6, padding: "3px 8px",
          cursor: "pointer", display: "flex", alignItems: "center", gap: 5, color: T.muted, fontSize: 11.5,
        }}>{copie ? <Check size={12} color={T.ok} /> : <Copy size={12} />}{copie ? "copié" : "copier"}</button>
      </div>
      <pre style={{ margin: 0, padding: 14, background: T.codeBg, color: T.codeInk, fontFamily: font.mono, fontSize: 12, lineHeight: 1.6, overflow: "auto", height: 420, flex: 1 }}>
        {contenu || "Code non disponible."}
      </pre>
    </div>
  );
}

function VueResultats({ resultat, allerA }) {
  const [iFichier, setIFichier] = useState(0);
  const [iModule, setIModule] = useState(0);
  const rapport = resultat?.rapport;
  const fichiers = rapport?.fichiers_migres || [];

  if (!fichiers.length) {
    return <Vide Icone={Gauge} titre="Pas encore de résultats" texte="Les résultats apparaissent ici à la fin d'une migration."
      action={<Bouton onClick={() => allerA("nouvelle")} Icone={Upload}>Nouvelle migration</Bouton>} />;
  }

  const fichier = fichiers[Math.min(iFichier, fichiers.length - 1)];
  const modules = fichier?.modules || [];
  const module = modules[Math.min(iModule, Math.max(0, modules.length - 1))];
  const etat = module?.etat_structure || {};
  const nomPhp = nomCourt(fichier.source);

  const tous = fichiers.flatMap((f, fi) => (f.modules || []).map((_, mi) => [fi, mi]));
  const position = tous.findIndex(([fi, mi]) => fi === iFichier && mi === iModule);
  const aller = (delta) => { const c = tous[position + delta]; if (c) { setIFichier(c[0]); setIModule(c[1]); } };

  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0,250px) minmax(0,1fr)", gap: 18, alignItems: "start" }}>
      <Carte style={{ padding: 14 }}>
        <div style={{ fontSize: 12, color: T.faint, textTransform: "uppercase", letterSpacing: ".08em", fontWeight: 500, padding: "4px 6px 10px" }}>Structure du projet</div>
        {fichiers.map((f, fi) => (
          <div key={fi} style={{ marginBottom: 6 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, padding: 6, fontSize: 13.5, color: T.ink, fontWeight: 500 }}>
              <Folder size={15} color={T.faint} /> {versPy(nomCourt(f.source))}
            </div>
            {(f.modules || []).map((m, mi) => {
              const actif = fi === iFichier && mi === iModule;
              const ton = TON_VERDICT[m.decision_finale] || TON_VERDICT.ITERER;
              return (
                <button key={mi} onClick={() => { setIFichier(fi); setIModule(mi); }} style={{
                  display: "flex", alignItems: "center", gap: 8, width: "100%", padding: "7px 8px 7px 28px",
                  border: "none", borderRadius: 8, cursor: "pointer", textAlign: "left",
                  background: actif ? "#EEF4FA" : "transparent", fontFamily: font.mono, fontSize: 12.5,
                  color: actif ? T.pyInk : T.muted, fontWeight: actif ? 600 : 400,
                }}>
                  <span style={{ width: 7, height: 7, borderRadius: "50%", background: ton.encre, flexShrink: 0 }} />
                  <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.nom_python}</span>
                  <span style={{ color: ton.encre, fontFamily: font.body, fontSize: 11.5 }}>{(m.score_final ?? 0).toFixed(0)}%</span>
                </button>
              );
            })}
          </div>
        ))}
        {rapport.statistiques && (
          <div style={{ borderTop: `1px solid ${T.line}`, marginTop: 8, padding: "12px 6px 2px", fontSize: 12.5, color: T.muted, lineHeight: 1.8 }}>
            <div><strong style={{ color: T.ink }}>{rapport.statistiques.fichiers_livres}</strong> fichier(s) livré(s) sur {rapport.statistiques.total_fichiers}</div>
            {rapport.cache && <div>Cache : {(rapport.cache.taux_reutilisation * 100).toFixed(0)}% de réutilisation</div>}
            {rapport.orchestrateurs_utilises?.length > 0 && <div>Orchestrateur : {rapport.orchestrateurs_utilises.join(", ")}</div>}
          </div>
        )}
      </Carte>

      <div style={{ display: "grid", gap: 18, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12.5, color: T.faint }}>{nomPhp} → {versPy(nomPhp)}</div>
            <div style={{ fontFamily: font.display, fontSize: 20, fontWeight: 600, color: T.ink, letterSpacing: "-.01em" }}>{module?.nom_python}</div>
          </div>
          <Bouton secondaire desactive={position <= 0} onClick={() => aller(-1)} Icone={ChevronLeft}>Module précédent</Bouton>
          <Bouton secondaire desactive={position >= tous.length - 1} onClick={() => aller(1)} Icone={ChevronRight}>Module suivant</Bouton>
        </div>

        <Confiance confiance={etat.derniere_decision?.confiance} score={module?.score_final} verdict={module?.decision_finale} />
        <Preuves key={`${iFichier}-${iModule}`} module={module} />

        <Carte style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) minmax(0,1fr)" }}>
            <div style={{ borderRight: `1px solid ${T.line}`, minWidth: 0 }}>
              <PanneauCode etiquette="PHP d'origine" titre={nomPhp} couleur={T.php} contenu={resultat.fichiers_php?.[nomPhp]} />
            </div>
            <PanneauCode etiquette="Python généré" titre={fichier.cible} couleur={T.py} contenu={resultat.fichiers_python?.[fichier.cible]} />
          </div>
          {(etat.versions?.code_python > 1 || etat.bascules_modele?.length > 0 || etat.replanifications > 0) && (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", padding: "10px 14px", borderTop: `1px solid ${T.line}` }}>
              {etat.versions?.code_python > 1 && <Etiquette><RotateCcw size={11} /> {etat.versions.code_python} versions générées</Etiquette>}
              {etat.replanifications > 0 && <Etiquette ton="warn">{etat.replanifications} révision(s) du plan</Etiquette>}
              {etat.bascules_modele?.length > 0 && <Etiquette ton="warn">orchestrateur basculé vers {etat.bascules_modele.at(-1).vers}</Etiquette>}
            </div>
          )}
        </Carte>
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────
   VUE 4 — ARCHITECTURE
──────────────────────────────────────────────── */
function VueArchitecture() {
  const gardeFous = [
    ["Checklist du Réviseur", "Aucune décision tant que les quatre vérifications n'ont pas été faites."],
    ["Invalidation automatique", "Un code régénéré rend périmées les vérifications précédentes."],
    ["Détection de stagnation", "Si le score ne progresse plus sur deux cycles, la boucle s'arrête."],
    ["Budget de tentatives", "Au-delà du maximum de corrections, le module part en validation humaine."],
    ["Décision non déléguée", "Si l'orchestration s'interrompt, le module n'est jamais livré par défaut."],
    ["Repli d'orchestrateur", "En cas de panne d'un fournisseur, la mission reprend sur l'autre, et c'est tracé."],
  ];
  const poids = [["Fonctionnel", 45, "Testeur"], ["Sécurité", 30, "Auditeur"], ["Comportemental", 15, "Comparateur"], ["Propriétés", 10, "Vérificateur de propriétés"]];

  return (
    <div style={{ display: "grid", gap: 18 }}>
      <Carte style={{ padding: 26 }}>
        <Titre niveau={1}>Le LLM coordonne, les règles valident</Titre>
        <p style={{ margin: 0, fontSize: 14, color: T.muted, maxWidth: 780, lineHeight: 1.6 }}>
          Le Manager choisit quel agent intervient, à partir de l'état partagé du module : l'ordre n'est pas fixé à l'avance.
          En revanche, aucun verdict ne vient de lui. Les vérifications et la décision finale sont des calculs déterministes,
          qui peuvent refuser ses choix.
        </p>
      </Carte>

      <div>
        <div style={{ fontSize: 12, color: T.faint, textTransform: "uppercase", letterSpacing: ".08em", fontWeight: 500, margin: "4px 2px 10px" }}>Les agents</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0,1fr))", gap: 12 }}>
          {Object.entries(AGENTS).map(([nom, a]) => (
            <Carte key={nom} style={{ padding: 16, borderColor: nom === "Manager" ? "#BFD3E6" : T.line }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                <div style={{ width: 32, height: 32, borderRadius: 8, background: nom === "Manager" ? T.nuit : "#EEF4FA", display: "grid", placeItems: "center" }}>
                  <a.Icone size={16} color={nom === "Manager" ? T.jaune : T.pyInk} />
                </div>
                <div style={{ fontWeight: 600, fontSize: 14, color: T.ink, flex: 1 }}>{nom}</div>
                <Etiquette ton={a.nature === "LLM" ? "warn" : "neutre"}>{a.nature}</Etiquette>
              </div>
              <div style={{ fontSize: 13, color: T.muted, lineHeight: 1.5 }}>{a.role}</div>
            </Carte>
          ))}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.3fr) minmax(0,1fr)", gap: 18, alignItems: "start" }}>
        <Carte style={{ padding: 22 }}>
          <Titre>Les garde-fous</Titre>
          <div style={{ display: "grid", gap: 12 }}>
            {gardeFous.map(([titre, texte]) => (
              <div key={titre} style={{ display: "flex", gap: 10 }}>
                <Lock size={15} color={T.pyInk} style={{ flexShrink: 0, marginTop: 2 }} />
                <div>
                  <div style={{ fontSize: 13.5, fontWeight: 600, color: T.ink }}>{titre}</div>
                  <div style={{ fontSize: 13, color: T.muted }}>{texte}</div>
                </div>
              </div>
            ))}
          </div>
        </Carte>
        <Carte style={{ padding: 22 }}>
          <Titre>Le score de confiance</Titre>
          <div style={{ display: "grid", gap: 12 }}>
            {poids.map(([nom, p, agent]) => (
              <div key={nom}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 5 }}>
                  <span style={{ color: T.ink, fontWeight: 500 }}>{nom}<span style={{ color: T.faint, fontWeight: 400 }}>, {agent}</span></span>
                  <span style={{ color: T.muted }}>{p}%</span>
                </div>
                <div style={{ height: 6, background: T.bg, borderRadius: 3, border: `1px solid ${T.line}` }}>
                  <div style={{ width: `${p}%`, height: "100%", background: T.py, borderRadius: 3 }} />
                </div>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 14, fontSize: 12.5, color: T.muted, lineHeight: 1.6 }}>
            Un critère non mesurable voit son poids redistribué sur les autres. Un critère sous 60 % ramène la confiance à « faible », quelle que soit la moyenne.
          </div>
        </Carte>
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────
   APPLICATION
──────────────────────────────────────────────── */
export default function App() {
  const [vue, setVue] = useState("nouvelle");
  const [sante, setSante] = useState(null);
  const [tache, setTache] = useState(null);
  const [resultat, setResultat] = useState(null);
  const [erreur, setErreur] = useState(null);
  const minuteur = useRef(null);
  const enCours = tache?.statut === "en_cours";

  useEffect(() => {
    axios.get(`${API_URL}/sante`).then((r) => setSante(r.data)).catch(() => setSante(null));
  }, []);

  /* Sondage de l'avancement : c'est ce qui rend le suivi vivant. */
  useEffect(() => {
    if (!tache?.id || tache.statut !== "en_cours") return;
    minuteur.current = setInterval(async () => {
      try {
        const { data } = await axios.get(`${API_URL}/jobs/${tache.id}`);
        setTache(data);
        if (data.statut === "termine") { setResultat(data.resultat); setVue("resultats"); }
      } catch {
        setErreur("Le serveur ne répond plus. Vérifie que l'API tourne.");
      }
    }, 1500);
    return () => clearInterval(minuteur.current);
  }, [tache?.id, tache?.statut]);

  const lancer = useCallback(async (fichier) => {
    setErreur(null); setResultat(null);
    const fd = new FormData();
    fd.append("fichier", fichier);
    const endpoint = fichier.name.toLowerCase().endsWith(".zip") ? "/migrer-projet" : "/migrer";
    try {
      const { data } = await axios.post(`${API_URL}${endpoint}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      setTache({ ...data, statut: "en_cours", libelle: fichier.name });
      setVue("suivi");
    } catch (e) {
      setErreur(e.response?.data?.detail || e.message);
    }
  }, []);

  return (
    <div style={{ minHeight: "100vh", background: T.bg, fontFamily: font.body, color: T.muted, textAlign: "left", fontSize: 14, lineHeight: 1.5 }}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;600&display=swap');
        @keyframes tourne { to { transform: rotate(360deg); } }`}</style>
      <BarreHaute sante={sante} tache={tache} resultat={resultat} />
      <div style={{
        display: "flex", alignItems: "flex-start", minHeight: "calc(100vh - 68px)",
        background: `linear-gradient(to right, ${T.surface} 231px, ${T.line} 231px, ${T.line} 232px, ${T.bg} 232px)`,
      }}>
        <BarreLaterale vue={vue} setVue={setVue} enCours={enCours} sante={sante} />
        <main style={{ flex: 1, minWidth: 0, padding: "24px 28px 40px" }}>
          <div style={{ maxWidth: 1180, margin: "0 auto" }}>
            {erreur && <Carte style={{ padding: 14, marginBottom: 16, background: T.errBg, borderColor: "#E9B8B8", color: T.err, fontSize: 13 }}>{erreur}</Carte>}
            {vue === "nouvelle" && <VueNouvelle onLance={lancer} occupe={enCours} sante={sante} />}
            {vue === "suivi" && <VueSuivi tache={tache} resultat={resultat} allerA={setVue} />}
            {vue === "resultats" && <VueResultats resultat={resultat} allerA={setVue} />}
            {vue === "architecture" && <VueArchitecture />}
          </div>
        </main>
      </div>
    </div>
  );
}