import { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import {
  Upload, FolderArchive, FileCode2, Copy, Check, ChevronRight,
  ShieldCheck, FlaskConical, Scale, Search, DraftingCompass,
  Code2, TestTube2, GitCompare, AlertTriangle, Ban, Clock,
  Layers, Database, Activity
} from "lucide-react";

const API_URL = "http://localhost:8000";

/* ────────────────────────────────────────────────
   TOKENS
──────────────────────────────────────────────── */
const T = {
  bg: "#F6F7F9", surface: "#FFFFFF", ink: "#0F1B2D", muted: "#5B6B7F",
  faint: "#8A97A8", line: "#E3E8EF", php: "#6E72B8", py: "#2F6FA7",
  pyDark: "#24567F", accent: "#F2C94C",
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

/* Les huit agents du système, dans l'ordre logique du pipeline.
   Le Manager n'exécute rien lui-même : il décide qui intervient. */
const AGENTS = {
  "Manager": { Icone: Layers, couleur: T.ink, role: "Décide qui intervient, à partir de l'état du module" },
  "Analyste": { Icone: Search, couleur: T.php, role: "Tree-sitter · failles CWE · invariants de sécurité" },
  "Architecte": { Icone: DraftingCompass, couleur: T.php, role: "Pattern de migration · découpage · révision du plan" },
  "Développeur": { Icone: Code2, couleur: T.py, role: "RAG (FAISS + CodeBERT) · génération du code Python" },
  "Testeur": { Icone: TestTube2, couleur: T.py, role: "Syntaxe · invariants · failles corrigées" },
  "Comparateur": { Icone: GitCompare, couleur: T.py, role: "Exécute PHP et Python sur les mêmes entrées" },
  "Vérificateur de propriétés": { Icone: FlaskConical, couleur: T.py, role: "Exécution symbolique (CrossHair · Z3)" },
  "Auditeur": { Icone: ShieldCheck, couleur: T.py, role: "Bandit · pip-audit · protections préservées" },
  "Réviseur": { Icone: Scale, couleur: T.ink, role: "Score de confiance · livrer, corriger ou escalader" },
};

const LIBELLE_CRITERE = {
  fonctionnel: "Fonctionnel",
  securite: "Sécurité",
  comportemental: "Comportemental",
  proprietes: "Propriétés",
};

const couleurScore = (s) => (s >= 80 ? T.ok : s >= 60 ? T.warn : T.err);

const TON_VERDICT = {
  LIVRER: { fond: T.okBg, encre: T.ok, texte: "Livré" },
  ITERER: { fond: T.warnBg, encre: T.warn, texte: "Correction demandée" },
  REANALYSE_COMPLETE: { fond: T.warnBg, encre: T.warn, texte: "Ré-analyse" },
  REPLANIFIER: { fond: T.warnBg, encre: T.warn, texte: "Plan à réviser" },
  ESCALADE_HUMAINE: { fond: T.errBg, encre: T.err, texte: "Reprise humaine" },
  ARRET_ECHEC: { fond: T.errBg, encre: T.err, texte: "Échec" },
};

/* ────────────────────────────────────────────────
   BRIQUES
──────────────────────────────────────────────── */
function Carte({ children, style }) {
  return (
    <div style={{
      background: T.surface, border: `1px solid ${T.line}`,
      borderRadius: T.radius, boxShadow: T.shadow, ...style,
    }}>{children}</div>
  );
}

function Etiquette({ children, ton = "neutre" }) {
  const tons = {
    neutre: [T.bg, T.muted], ok: [T.okBg, T.ok],
    warn: [T.warnBg, T.warn], err: [T.errBg, T.err],
  };
  const [fond, encre] = tons[ton] || tons.neutre;
  return (
    <span style={{
      background: fond, color: encre, fontFamily: font.mono, fontSize: 11,
      padding: "3px 8px", borderRadius: 6, letterSpacing: ".02em",
      whiteSpace: "nowrap",
    }}>{children}</span>
  );
}

function TitreSection({ children, apres }) {
  return (
    <div style={{
      display: "flex", alignItems: "baseline", justifyContent: "space-between",
      marginBottom: 14,
    }}>
      <h2 style={{
        fontFamily: font.display, fontSize: 15, fontWeight: 600,
        color: T.ink, margin: 0, letterSpacing: "-.01em",
      }}>{children}</h2>
      {apres}
    </div>
  );
}

/* ────────────────────────────────────────────────
   ZONE 1 — LE SCORE DE CONFIANCE
   Le cœur de la démonstration : la décision ne repose pas sur un
   verdict binaire mais sur quatre critères mesurés séparément, dont
   le poids est redistribué quand l'un d'eux n'est pas mesurable.
──────────────────────────────────────────────── */
function Confiance({ confiance, score, verdict }) {
  if (!confiance) {
    return (
      <Carte style={{ padding: 20 }}>
        <div style={{ color: T.faint, fontSize: 13 }}>
          Détail des critères indisponible (module migré en mode direct).
        </div>
      </Carte>
    );
  }
  const ton = TON_VERDICT[verdict] || TON_VERDICT.ITERER;
  const niveau = { elevee: "élevée", moyenne: "moyenne", faible: "faible" };

  return (
    <Carte style={{ padding: 22 }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 28 }}>
        <div style={{ minWidth: 150 }}>
          <div style={{
            fontFamily: font.mono, fontSize: 11, color: T.faint,
            textTransform: "uppercase", letterSpacing: ".1em",
          }}>Score de confiance</div>
          <div style={{
            fontFamily: font.display, fontSize: 44, fontWeight: 600,
            color: couleurScore(score || 0), lineHeight: 1.1, marginTop: 4,
          }}>{(score ?? 0).toFixed(1)}<span style={{ fontSize: 22 }}>%</span></div>
          <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
            <span style={{
              background: ton.fond, color: ton.encre, fontSize: 12,
              fontWeight: 600, padding: "4px 10px", borderRadius: 6,
            }}>{ton.texte}</span>
            <Etiquette>confiance {niveau[confiance.niveau] || confiance.niveau}</Etiquette>
          </div>
        </div>

        <div style={{ flex: 1, display: "grid", gap: 12 }}>
          {(confiance.criteres || []).map((c) => (
            <div key={c.nom}>
              <div style={{
                display: "flex", justifyContent: "space-between",
                fontSize: 12.5, marginBottom: 5,
              }}>
                <span style={{ color: c.mesure ? T.ink : T.faint, fontWeight: 500 }}>
                  {LIBELLE_CRITERE[c.nom] || c.nom}
                  <span style={{ color: T.faint, fontWeight: 400 }}> · {c.agent}</span>
                </span>
                <span style={{
                  fontFamily: font.mono, fontSize: 12,
                  color: c.mesure ? couleurScore(c.score) : T.faint,
                }}>
                  {c.mesure
                    ? `${c.score.toFixed(0)}% · poids ${(c.poids * 100).toFixed(0)}%`
                    : "non mesuré"}
                </span>
              </div>
              <div style={{
                height: 6, background: T.bg, borderRadius: 3, overflow: "hidden",
                border: `1px solid ${T.line}`,
              }}>
                {c.mesure && (
                  <div style={{
                    width: `${Math.max(0, Math.min(100, c.score))}%`, height: "100%",
                    background: couleurScore(c.score), transition: "width .5s ease",
                  }} />
                )}
              </div>
              {!c.mesure && c.raison && (
                <div style={{ fontSize: 11.5, color: T.faint, marginTop: 4 }}>
                  {c.raison} — son poids est redistribué sur les autres critères
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </Carte>
  );
}

/* ────────────────────────────────────────────────
   ZONE 2 — LE JOURNAL DU MANAGER
   Chaque ligne est une sollicitation, avec la raison donnée par le
   Manager. Les refus du Réviseur y sont visibles : c'est ce qui
   montre que la validation ne dépend pas du LLM orchestrateur.
──────────────────────────────────────────────── */
const TON_ISSUE = {
  execute: { ton: "ok", texte: "exécuté" },
  cache: { ton: "neutre", texte: "réutilisé (cache)" },
  deja_fait: { ton: "neutre", texte: "déjà fait" },
  refus_prerequis: { ton: "warn", texte: "refusé — prérequis" },
  indisponible: { ton: "err", texte: "indisponible" },
};

function Journal({ journal, enCours }) {
  const [ouvert, setOuvert] = useState(null);
  const bas = useRef(null);

  useEffect(() => {
    if (enCours && bas.current) bas.current.scrollIntoView({ behavior: "smooth" });
  }, [journal?.length, enCours]);

  if (!journal?.length) {
    return (
      <div style={{ color: T.faint, fontSize: 13, padding: "18px 0" }}>
        {enCours ? "En attente de la première sollicitation…"
                 : "Aucune sollicitation enregistrée."}
      </div>
    );
  }

  return (
    <div style={{ position: "relative" }}>
      <div style={{
        position: "absolute", left: 15, top: 10, bottom: 10, width: 1,
        background: T.line,
      }} />
      {journal.map((entree, i) => {
        const agent = AGENTS[entree.agent] || {};
        const Icone = agent.Icone || Activity;
        const issue = TON_ISSUE[entree.issue] || { ton: "neutre", texte: entree.issue };
        const estOuvert = ouvert === i;
        return (
          <div key={i} style={{ position: "relative", paddingLeft: 42, paddingBottom: 12 }}>
            <div style={{
              position: "absolute", left: 4, top: 2, width: 24, height: 24,
              borderRadius: "50%", background: T.surface,
              border: `1px solid ${issue.ton === "err" ? T.err
                : issue.ton === "warn" ? T.warn : T.line}`,
              display: "grid", placeItems: "center",
            }}>
              <Icone size={13} color={agent.couleur || T.muted} />
            </div>

            <button
              onClick={() => setOuvert(estOuvert ? null : i)}
              style={{
                width: "100%", textAlign: "left", background: "none",
                border: "none", padding: 0, cursor: "pointer", font: "inherit",
              }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontWeight: 600, fontSize: 13.5, color: T.ink }}>
                  {entree.agent}
                </span>
                <Etiquette ton={issue.ton}>{issue.texte}</Etiquette>
                {entree.iteration > 1 && (
                  <Etiquette>itération {entree.iteration}</Etiquette>
                )}
                <ChevronRight size={13} color={T.faint} style={{
                  marginLeft: "auto",
                  transform: estOuvert ? "rotate(90deg)" : "none",
                  transition: "transform .2s",
                }} />
              </div>
              {entree.justification_manager && (
                <div style={{
                  fontSize: 12.5, color: T.muted, marginTop: 3,
                  overflow: "hidden", textOverflow: "ellipsis",
                  whiteSpace: estOuvert ? "normal" : "nowrap",
                }}>
                  {entree.justification_manager}
                </div>
              )}
            </button>

            {estOuvert && (
              <div style={{
                marginTop: 8, padding: 12, background: T.bg,
                borderRadius: 8, fontSize: 12.5, color: T.muted,
                border: `1px solid ${T.line}`,
              }}>
                <div style={{ marginBottom: 6 }}>
                  <strong style={{ color: T.ink }}>Rôle</strong> — {agent.role || "—"}
                </div>
                {entree.etapes_restantes_avant?.length > 0 && (
                  <div>
                    <strong style={{ color: T.ink }}>Restait à faire</strong> —{" "}
                    {entree.etapes_restantes_avant.join(", ")}
                  </div>
                )}
                {entree.horodatage && (
                  <div style={{ marginTop: 6, fontFamily: font.mono, fontSize: 11 }}>
                    {entree.horodatage}
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
      <div ref={bas} />
    </div>
  );
}

/* ────────────────────────────────────────────────
   ZONE 3 — LES PREUVES
──────────────────────────────────────────────── */
function Preuves({ module }) {
  const [onglet, setOnglet] = useState("comportement");
  const eq = module?.equivalence || {};
  const formel = module?.verification_formelle || {};
  const etat = module?.etat_structure || {};

  const onglets = [
    { id: "comportement", titre: "Comportement", Icone: GitCompare },
    { id: "proprietes", titre: "Propriétés", Icone: FlaskConical },
    { id: "attention", titre: "Points d'attention", Icone: AlertTriangle },
  ];

  return (
    <Carte style={{ padding: 0, overflow: "hidden" }}>
      <div style={{ display: "flex", borderBottom: `1px solid ${T.line}` }}>
        {onglets.map(({ id, titre, Icone }) => (
          <button key={id} onClick={() => setOnglet(id)} style={{
            flex: 1, padding: "12px 10px", background: onglet === id ? T.surface : T.bg,
            border: "none", borderBottom: onglet === id ? `2px solid ${T.py}` : "2px solid transparent",
            cursor: "pointer", fontFamily: font.body, fontSize: 12.5,
            color: onglet === id ? T.ink : T.muted, fontWeight: onglet === id ? 600 : 400,
            display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
          }}>
            <Icone size={13} /> {titre}
          </button>
        ))}
      </div>

      <div style={{ padding: 18, fontSize: 13 }}>
        {onglet === "comportement" && (
          eq.statut === "teste" ? (
            <div style={{ display: "grid", gap: 12 }}>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <Etiquette ton={eq.score_equivalence >= 0.9 ? "ok" : "warn"}>
                  {((eq.score_equivalence || 0) * 100).toFixed(0)}% d'équivalence
                </Etiquette>
                <Etiquette>{eq.cas_testes} cas exécutés</Etiquette>
                {eq.base_simulee && (
                  <Etiquette>base simulée · {(eq.base_simulee.tables || []).join(", ")}</Etiquette>
                )}
              </div>

              {eq.injections_bloquees?.length > 0 && (
                <div style={{
                  background: T.okBg, border: `1px solid ${T.ok}33`,
                  borderRadius: 8, padding: 12,
                }}>
                  <div style={{ color: T.ok, fontWeight: 600, marginBottom: 6,
                    display: "flex", alignItems: "center", gap: 6 }}>
                    <Ban size={14} /> {eq.injections_bloquees.length} injection(s) neutralisée(s)
                  </div>
                  <div style={{ color: T.muted, fontSize: 12.5, marginBottom: 8 }}>
                    Le PHP d'origine accepte ces entrées, le Python les bloque.
                    L'écart est volontaire : la faille est corrigée, ce n'est pas
                    une régression.
                  </div>
                  {eq.injections_bloquees.map((v, i) => (
                    <div key={i} style={{
                      fontFamily: font.mono, fontSize: 11.5, color: T.ink,
                      background: T.surface, padding: "4px 8px", borderRadius: 5,
                      marginBottom: 4,
                    }}>{v}</div>
                  ))}
                </div>
              )}

              {eq.divergences?.length > 0 ? (
                <div>
                  <div style={{ fontWeight: 600, color: T.ink, marginBottom: 6 }}>
                    {eq.divergences.length} divergence(s)
                  </div>
                  {eq.divergences.slice(0, 6).map((d, i) => (
                    <div key={i} style={{
                      borderLeft: `2px solid ${T.err}`, paddingLeft: 10,
                      marginBottom: 8, fontSize: 12.5,
                    }}>
                      <div style={{ fontFamily: font.mono, fontSize: 11.5, color: T.faint }}>
                        {d.type} · entrée {JSON.stringify(d.entree)}
                      </div>
                      <div style={{ color: T.muted }}>
                        PHP : {JSON.stringify(d.php)?.slice(0, 90)}
                      </div>
                      <div style={{ color: T.muted }}>
                        Python : {JSON.stringify(d.python)?.slice(0, 90)}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ color: T.ok }}>
                  Aucune divergence : le Python se comporte comme le PHP sur
                  toutes les entrées testées.
                </div>
              )}
            </div>
          ) : (
            <div style={{ color: T.muted }}>
              Équivalence non testée{eq.statut ? ` (${eq.statut})` : ""}.
              {eq.raison && <div style={{ marginTop: 6, color: T.faint }}>{eq.raison}</div>}
            </div>
          )
        )}

        {onglet === "proprietes" && (
          formel.proprietes?.length ? (
            <div style={{ display: "grid", gap: 8 }}>
              <div style={{ color: T.faint, fontSize: 12, marginBottom: 2 }}>
                « Prouvée » signifie : aucun contre-exemple trouvé par
                exploration symbolique dans le budget de temps — une
                vérification bornée, non une preuve absolue.
              </div>
              {formel.proprietes.map((p, i) => (
                <div key={i} style={{
                  display: "flex", gap: 10, alignItems: "flex-start",
                  padding: "8px 10px", background: T.bg, borderRadius: 8,
                }}>
                  <Etiquette ton={p.statut === "prouvee" ? "ok"
                    : p.statut === "refutee" ? "err" : "neutre"}>
                    {p.statut}
                  </Etiquette>
                  <div style={{ flex: 1 }}>
                    <div style={{ color: T.ink }}>{p.libelle}</div>
                    <div style={{ fontSize: 11.5, color: T.faint }}>{p.famille}</div>
                    {p.contre_exemple && (
                      <div style={{
                        fontFamily: font.mono, fontSize: 11.5, color: T.err,
                        marginTop: 4,
                      }}>contre-exemple Z3 : {p.contre_exemple}</div>
                    )}
                    {p.raison && (
                      <div style={{ fontSize: 11.5, color: T.faint, marginTop: 4 }}>
                        {p.raison}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ color: T.muted }}>Aucune propriété vérifiée sur ce module.</div>
          )
        )}

        {onglet === "attention" && (
          etat.points_attention?.length ? (
            <div style={{ display: "grid", gap: 8 }}>
              {etat.points_attention.map((p, i) => (
                <div key={i} style={{
                  display: "flex", gap: 8, alignItems: "flex-start",
                  color: T.muted, fontSize: 12.5,
                }}>
                  <AlertTriangle size={14} color={T.warn} style={{ flexShrink: 0, marginTop: 2 }} />
                  <span>{p}</span>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ color: T.muted }}>Aucun point d'attention signalé.</div>
          )
        )}
      </div>
    </Carte>
  );
}

/* ────────────────────────────────────────────────
   CODE
──────────────────────────────────────────────── */
function Code({ titre, contenu, couleur = T.py, versions }) {
  const [copie, setCopie] = useState(false);
  const copier = () => {
    navigator.clipboard.writeText(contenu || "");
    setCopie(true);
    setTimeout(() => setCopie(false), 1400);
  };
  return (
    <Carte style={{ padding: 0, overflow: "hidden", display: "flex", flexDirection: "column" }}>
      <div style={{
        display: "flex", alignItems: "center", gap: 8, padding: "10px 14px",
        borderBottom: `1px solid ${T.line}`,
      }}>
        <FileCode2 size={14} color={couleur} />
        <span style={{ fontFamily: font.mono, fontSize: 12, color: T.ink }}>{titre}</span>
        {versions > 1 && <Etiquette>{versions} versions générées</Etiquette>}
        <button onClick={copier} style={{
          marginLeft: "auto", background: "none", border: `1px solid ${T.line}`,
          borderRadius: 6, padding: "4px 8px", cursor: "pointer",
          display: "flex", alignItems: "center", gap: 5, color: T.muted, fontSize: 11.5,
        }}>
          {copie ? <Check size={12} color={T.ok} /> : <Copy size={12} />}
          {copie ? "copié" : "copier"}
        </button>
      </div>
      <pre style={{
        margin: 0, padding: 14, background: T.codeBg, color: T.codeInk,
        fontFamily: font.mono, fontSize: 12, lineHeight: 1.6,
        overflow: "auto", maxHeight: 420, flex: 1,
      }}>{contenu || "—"}</pre>
    </Carte>
  );
}

/* ────────────────────────────────────────────────
   DÉPÔT / ENVOI
──────────────────────────────────────────────── */
function Depot({ onLance, occupe }) {
  const [fichier, setFichier] = useState(null);
  const [survol, setSurvol] = useState(false);
  const champ = useRef(null);

  const choisir = (f) => f && setFichier(f);

  return (
    <Carte style={{ padding: 20 }}>
      <TitreSection>Migration</TitreSection>
      <div
        onDragOver={(e) => { e.preventDefault(); setSurvol(true); }}
        onDragLeave={() => setSurvol(false)}
        onDrop={(e) => {
          e.preventDefault(); setSurvol(false);
          choisir(e.dataTransfer.files?.[0]);
        }}
        onClick={() => champ.current?.click()}
        style={{
          border: `1.5px dashed ${survol ? T.py : T.line}`,
          background: survol ? "#F0F6FB" : T.bg,
          borderRadius: 10, padding: "26px 18px", textAlign: "center",
          cursor: "pointer", transition: "all .2s",
        }}>
        <input ref={champ} type="file" accept=".zip,.php" hidden
          onChange={(e) => choisir(e.target.files?.[0])} />
        {fichier ? (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
            {fichier.name.endsWith(".zip")
              ? <FolderArchive size={16} color={T.py} />
              : <FileCode2 size={16} color={T.php} />}
            <span style={{ color: T.ink, fontSize: 13.5 }}>{fichier.name}</span>
          </div>
        ) : (
          <>
            <Upload size={20} color={T.faint} />
            <div style={{ marginTop: 8, fontSize: 13.5, color: T.muted }}>
              Dépose une application PHP (.zip) ou un fichier .php
            </div>
          </>
        )}
      </div>

      <button
        disabled={!fichier || occupe}
        onClick={() => onLance(fichier)}
        style={{
          width: "100%", marginTop: 14, padding: "11px 16px",
          background: !fichier || occupe ? T.line : T.py, color: "#fff",
          border: "none", borderRadius: 9, fontFamily: font.body,
          fontSize: 14, fontWeight: 600,
          cursor: !fichier || occupe ? "default" : "pointer",
        }}>
        {occupe ? "Migration en cours…" : "Lancer la migration"}
      </button>
    </Carte>
  );
}

/* ────────────────────────────────────────────────
   ENVIRONNEMENT
──────────────────────────────────────────────── */
function Environnement() {
  const [sante, setSante] = useState(null);
  useEffect(() => {
    axios.get(`${API_URL}/sante`).then((r) => setSante(r.data)).catch(() => {});
  }, []);
  if (!sante) return null;

  const points = [
    ["Génération", sante.modele_generation, true],
    ["Mode", sante.mode, true],
    ...(sante.mode === "orchestre" ? [
      ["Orchestrateur", sante.orchestrateur, true],
      ["Repli auto", sante.bascule_autorisee ? "actif" : "désactivé", true],
    ] : []),
    ["PHP", sante.php ? "disponible" : "absent", !!sante.php],
    ["pdo_sqlite", sante.pdo_sqlite ? "actif" : "absent", sante.pdo_sqlite],
    ["CrossHair", sante.crosshair ? "actif" : "absent", sante.crosshair],
  ];
  return (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
      {points.map(([cle, valeur, ok]) => (
        <span key={cle} style={{
          fontFamily: font.mono, fontSize: 11, color: ok ? T.muted : T.err,
          background: ok ? T.bg : T.errBg, border: `1px solid ${T.line}`,
          padding: "3px 8px", borderRadius: 6,
        }}>{cle} : {String(valeur)}</span>
      ))}
    </div>
  );
}

/* ────────────────────────────────────────────────
   APPLICATION
──────────────────────────────────────────────── */
export default function App() {
  const [tache, setTache] = useState(null);      // suivi de la migration
  const [resultat, setResultat] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [iFichier, setIFichier] = useState(0);
  const [iModule, setIModule] = useState(0);
  const minuteur = useRef(null);

  const enCours = tache?.statut === "en_cours";

  /* Sondage : tant que la migration tourne, on demande son
     avancement. C'est ce qui rend le journal vivant au lieu d'un
     écran figé pendant plusieurs minutes. */
  useEffect(() => {
    if (!tache?.id || tache.statut !== "en_cours") return;
    minuteur.current = setInterval(async () => {
      try {
        const { data } = await axios.get(`${API_URL}/jobs/${tache.id}`);
        setTache(data);
        if (data.statut === "termine") setResultat(data.resultat);
        if (data.statut === "echec") setErreur(data.erreur);
      } catch (e) {
        setErreur("Le serveur ne répond plus. Vérifie que l'API tourne.");
        setTache((t) => (t ? { ...t, statut: "echec" } : t));
      }
    }, 1500);
    return () => clearInterval(minuteur.current);
  }, [tache?.id, tache?.statut]);

  const lancer = useCallback(async (fichier) => {
    setErreur(null); setResultat(null); setIFichier(0); setIModule(0);
    const fd = new FormData();
    fd.append("fichier", fichier);
    const endpoint = fichier.name.toLowerCase().endsWith(".zip")
      ? "/migrer-projet" : "/migrer";
    try {
      const { data } = await axios.post(`${API_URL}${endpoint}`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setTache({ ...data, statut: "en_cours" });
    } catch (e) {
      setErreur(e.response?.data?.detail || e.message);
    }
  }, []);

  const rapport = resultat?.rapport;
  const fichiers = rapport?.fichiers_migres || [];
  const fichierCourant = fichiers[iFichier];
  const modules = fichierCourant?.modules || [];
  const moduleCourant = modules[iModule];
  const etat = moduleCourant?.etat_structure || {};
  const confiance = etat.derniere_decision?.confiance;
  const direct = tache?.en_direct;

  return (
    <div style={{
      minHeight: "100vh", background: T.bg, fontFamily: font.body,
      color: T.muted, padding: "26px 22px",
    }}>
      <div style={{ maxWidth: 1240, margin: "0 auto" }}>

        {/* En-tête */}
        <header style={{ marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
            <h1 style={{
              fontFamily: font.display, fontSize: 26, fontWeight: 700,
              color: T.ink, margin: 0, letterSpacing: "-.02em",
            }}>SMAML</h1>
            <span style={{ fontSize: 13.5 }}>
              Système multi-agents de modernisation de code legacy · PHP → Python
            </span>
          </div>
          <div style={{ marginTop: 10 }}><Environnement /></div>
        </header>

        {erreur && (
          <Carte style={{ padding: 14, marginBottom: 16, background: T.errBg,
            borderColor: `${T.err}44`, color: T.err, fontSize: 13 }}>
            {erreur}
          </Carte>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "340px 1fr", gap: 16, alignItems: "start" }}>

          {/* Colonne gauche : dépôt + journal */}
          <div style={{ display: "grid", gap: 16 }}>
            <Depot onLance={lancer} occupe={enCours} />

            <Carte style={{ padding: 20 }}>
              <TitreSection apres={
                enCours ? <Etiquette ton="warn"><Clock size={10} /> en cours</Etiquette>
                        : direct || etat.journal ? <Etiquette>{(direct?.journal || etat.journal || []).length} étapes</Etiquette>
                        : null
              }>Journal du Manager</TitreSection>

              {enCours && direct?.module && (
                <div style={{ fontSize: 12.5, marginBottom: 10, color: T.muted }}>
                  Module en cours : <strong style={{ color: T.ink }}>{direct.module}</strong>
                  {direct.tentatives > 0 && ` · ${direct.tentatives} correction(s)`}
                </div>
              )}

              <Journal
                journal={enCours ? direct?.journal : etat.journal}
                enCours={enCours} />
            </Carte>
          </div>

          {/* Colonne droite : décision, preuves, code */}
          <div style={{ display: "grid", gap: 16 }}>

            {!resultat && !enCours && (
              <Carte style={{ padding: 40, textAlign: "center" }}>
                <Database size={22} color={T.faint} />
                <div style={{ marginTop: 10, fontSize: 14 }}>
                  Dépose une application PHP pour lancer la migration.
                </div>
                <div style={{ marginTop: 6, fontSize: 12.5, color: T.faint }}>
                  Le journal se remplira agent par agent pendant le traitement.
                </div>
              </Carte>
            )}

            {enCours && (
              <Carte style={{ padding: 22 }}>
                <TitreSection>Vérifications du module en cours</TitreSection>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {Object.entries(direct?.etapes || {}).map(([nom, fait]) => (
                    <Etiquette key={nom} ton={fait ? "ok" : "neutre"}>
                      {fait ? "✓" : "·"} {nom.replace(/_/g, " ")}
                    </Etiquette>
                  ))}
                </div>
                {direct?.points_attention?.length > 0 && (
                  <div style={{ marginTop: 14, display: "grid", gap: 6 }}>
                    {direct.points_attention.slice(0, 4).map((p, i) => (
                      <div key={i} style={{ fontSize: 12.5, color: T.muted,
                        display: "flex", gap: 7 }}>
                        <AlertTriangle size={13} color={T.warn} style={{ flexShrink: 0, marginTop: 2 }} />
                        <span>{p}</span>
                      </div>
                    ))}
                  </div>
                )}
              </Carte>
            )}

            {resultat && (
              <>
                {/* Sélecteurs fichier / module */}
                <Carte style={{ padding: 14 }}>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: modules.length ? 10 : 0 }}>
                    {fichiers.map((f, i) => (
                      <button key={i} onClick={() => { setIFichier(i); setIModule(0); }} style={{
                        padding: "6px 12px", borderRadius: 7, cursor: "pointer",
                        border: `1px solid ${i === iFichier ? T.py : T.line}`,
                        background: i === iFichier ? "#F0F6FB" : T.surface,
                        color: i === iFichier ? T.py : T.muted,
                        fontFamily: font.mono, fontSize: 12,
                      }}>{f.source} → {f.cible}</button>
                    ))}
                  </div>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {modules.map((m, i) => {
                      const ton = TON_VERDICT[m.decision_finale] || TON_VERDICT.ITERER;
                      return (
                        <button key={i} onClick={() => setIModule(i)} style={{
                          padding: "5px 10px", borderRadius: 7, cursor: "pointer",
                          border: `1px solid ${i === iModule ? T.ink : T.line}`,
                          background: i === iModule ? T.surface : T.bg,
                          fontFamily: font.mono, fontSize: 11.5,
                          color: ton.encre, display: "flex", gap: 6, alignItems: "center",
                        }}>
                          {m.nom_python}
                          <span style={{ color: T.faint }}>
                            {(m.score_final ?? 0).toFixed(0)}%
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </Carte>

                <Confiance
                  confiance={confiance}
                  score={moduleCourant?.score_final}
                  verdict={moduleCourant?.decision_finale} />

                <Preuves module={moduleCourant} />

                <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 16 }}>
                  <Code
                    titre={fichierCourant?.cible || "module.py"}
                    contenu={resultat.fichiers_python?.[fichierCourant?.cible]}
                    versions={etat.versions?.code_python} />
                </div>

                {/* Bilan */}
                <Carte style={{ padding: 18 }}>
                  <TitreSection>Bilan</TitreSection>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <Etiquette ton="ok">
                      {rapport.statistiques?.fichiers_livres}/{rapport.statistiques?.total_fichiers} fichiers livrés
                    </Etiquette>
                    {rapport.cache && (
                      <Etiquette>
                        cache : {(rapport.cache.taux_reutilisation * 100).toFixed(0)}% de réutilisation
                      </Etiquette>
                    )}
                    {etat.replanifications > 0 && (
                      <Etiquette ton="warn">{etat.replanifications} révision(s) du plan</Etiquette>
                    )}
                    {etat.bascules_modele?.length > 0 && (
                      <Etiquette ton="warn">
                        orchestrateur basculé vers {etat.bascules_modele.at(-1).vers}
                      </Etiquette>
                    )}
                  </div>
                </Carte>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}