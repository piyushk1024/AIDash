import { useState } from "react";
import { api } from "../lib/api";

const initialStatus = {
  upload: "idle",
  semantics: "idle",
  plan: "idle",
  dashboard: "idle",
};

export function useDasher() {
  const [datasetId, setDatasetId] = useState(null);
  const [uploadResult, setUploadResult] = useState(null);
  const [semantics, setSemantics] = useState(null);
  const [plan, setPlan] = useState(null);
  const [pipelinePlan, setPipelinePlan] = useState(null);
  const [agentPlan, setAgentPlan] = useState(null);
  const [dashboardResult, setDashboardResult] = useState(null);
  const [agentResult, setAgentResult] = useState(null);

  const [conflict, setConflict] = useState(null);
  const [status, setStatus] = useState(initialStatus);
  const [errors, setErrors] = useState({});

  const setStepStatus = (step, value) =>
    setStatus((prev) => ({ ...prev, [step]: value }));
  const setStepError = (step, message) =>
    setErrors((prev) => ({ ...prev, [step]: message }));

  // ── Step 1: Upload ──────────────────────────────────────────
  async function upload(file, replace = false, forceNew = false) {
    setStepStatus("upload", "loading");
    setStepError("upload", null);
    try {
      const result = await api.uploadCsv(file, replace, forceNew);
      if (result.conflict) {
        setConflict({ file, existing_dataset_id: result.existing_dataset_id });
        setStepStatus("upload", "idle");
        return;
      }
      setConflict(null);
      setUploadResult(result);
      setDatasetId(result.dataset_id);
      setStepStatus("upload", "done");
    } catch (e) {
      setStepStatus("upload", "error");
      setStepError("upload", e.message);
    }
  }

  async function resolveConflict(choice) {
    if (!conflict) return;
    setConflict(null);
    if (choice === "replace") {
      await upload(conflict.file, true, false);
    } else {
      await upload(conflict.file, false, true);
    }
  }

  // ── Step 2: Semantics ───────────────────────────────────────
  async function inferSemantics(businessHint) {
    if (!datasetId) return;
    setStepStatus("semantics", "loading");
    setStepError("semantics", null);
    try {
      const result = await api.inferSemantics(datasetId, businessHint);
      setSemantics(result);
      setStepStatus("semantics", "done");
    } catch (e) {
      setStepStatus("semantics", "error");
      setStepError("semantics", e.message);
    }
  }

  // ── Step 3: Dashboard Plan (pipeline mode) ──────────────────
  async function generatePlan() {
    if (!datasetId) return;
    setStepStatus("plan", "loading");
    setStepError("plan", null);
    try {
      const result = await api.generatePlan(datasetId);
      setPlan(result);
      setPipelinePlan(result);
      setStepStatus("plan", "done");
    } catch (e) {
      setStepStatus("plan", "error");
      setStepError("plan", e.message);
    }
  }

  // ── Step 4: Build dashboard (pipeline mode) ─────────────────
  async function createDashboard() {
    if (!datasetId) return;
    setStepStatus("dashboard", "loading");
    setStepError("dashboard", null);
    try {
      const result = await api.buildDashboard(datasetId);
      setDashboardResult(result);
      setAgentResult(null);
      setStepStatus("dashboard", "done");
    } catch (e) {
      setStepStatus("dashboard", "error");
      setStepError("dashboard", e.message);
    }
  }
// ── One-shot launch: apply a finished /datasets/launch/stream run ──
  // Component owns useEventStream and calls startStream itself with a
  // FormData body; once the stream ends it hands the full collected
  // array + mode here. Mirrors rehydrate()'s end state so downstream
  // steps (semantics/plan/dashboard) read the same way post-launch.
  function applyLaunchEvents(events, mode) {
    const createdEvent = events.find(e => e.type === "dataset_created");
    if (createdEvent) {
      setDatasetId(createdEvent.dataset_id);
      setStepStatus("upload", "done");
    }

    const profileDone = events.find(e => e.type === "step_done" && e.phase === "profile");
    if (profileDone) {
      setUploadResult(prev => ({ ...(prev ?? {}), profile: profileDone.profile }));
    }

    const semanticsDone = events.find(e => e.type === "step_done" && e.phase === "semantics");
    if (semanticsDone) {
      setSemantics(semanticsDone.semantics);
      setStepStatus("semantics", "done");
    }

    const errorEvent = events.find(e => e.type === "phase_error");
    if (errorEvent) {
      setStepStatus(errorEvent.phase ?? "dashboard", "error");
      setStepError(errorEvent.phase ?? "dashboard", errorEvent.error);
      return;
    }

    if (mode === "pipeline") {
      const planDone = events.find(e => e.type === "step_done" && e.phase === "plan");
      if (planDone) {
        setPlan(planDone.plan);
        setPipelinePlan(planDone.plan);
        setStepStatus("plan", "done");
      }
      const finishEvent = events.find(e => e.type === "finish");
      if (finishEvent) {
        setDashboardResult({
          cards: finishEvent.charts_built,
          cards_created: finishEvent.charts_built.length,
          errors: finishEvent.errors,
        });
        setAgentResult(null);
        setStepStatus("dashboard", "done");
      }
    } else {
      applyAgentEvents(events, false);
    }
  }

  
  // ── Agent mode: apply a finished SSE run's collected events ──
  // Component owns useEventStream and calls startStream itself;
  // once the stream ends it hands the full collected array here.
  // rationale event is pulled out explicitly, everything else is trace.
  function applyAgentEvents(events, isNudge = false) {
    const finishEvent = events.find(e => e.type === "finish");
    const rationaleEvent = events.find(e => e.type === "rationale");
    const newTrace = events.filter(e => !["step_started", "healing", "rationale", "finish"].includes(e.type));

    setAgentResult(prev => ({
      published: false,
      charts_built: finishEvent?.charts_built ?? [],
      trace: isNudge ? [...(prev?.trace ?? []), ...newTrace] : newTrace,
      rationale: rationaleEvent?.text ?? (isNudge ? prev?.rationale ?? "" : ""),
      dashboard_title: rationaleEvent?.dashboard_title ?? (isNudge ? prev?.dashboard_title ?? "" : ""),
    }));

    setDashboardResult(null);
    setStepStatus("dashboard", "done");
  }

  // ── Rehydrate from /state ───────────────────────────────────
  async function rehydrate(id) {
    try {
      const state = await api.getDatasetState(id);
      const {
        upload_result,
        semantics: sem,
        pipeline_plan,
        agent_plan,
        dashboard_result,
        agent_result,
      } = state;

      setDatasetId(id);
      setUploadResult(upload_result);
      setSemantics(sem);
      setPipelinePlan(pipeline_plan);
      setAgentPlan(agent_plan);
      setPlan(pipeline_plan);

      if (agent_result) {
        setAgentResult(agent_result);
        setDashboardResult(null);
      } else {
        setDashboardResult(dashboard_result);
        setAgentResult(null);
      }

      setStatus({
        upload:    upload_result ? "done" : "idle",
        semantics: sem ? "done" : "idle",
        plan:      pipeline_plan ? "done" : "idle",
        dashboard: (agent_result || dashboard_result) ? "done" : "idle",
      });
    } catch (e) {
      console.error("Rehydrate failed:", e.message);
    }
  }

  function reset() {
    setDatasetId(null);
    setUploadResult(null);
    setSemantics(null);
    setPlan(null);
    setPipelinePlan(null);
    setAgentPlan(null);
    setDashboardResult(null);
    setAgentResult(null);
    setStatus(initialStatus);
    setErrors({});
  }

  // ── Card mutation helpers (NL add/edit/delete) ──────────────
  function addCard(card) {
    setDashboardResult(prev => ({
      ...prev,
      cards: [...(prev.cards ?? []), card],
      cards_created: (prev.cards_created ?? 0) + 1,
    }));
  }

  function replaceCard(cardId, card) {
    setDashboardResult(prev => ({
      ...prev,
      cards: (prev.cards ?? []).map(c => c.card_id === cardId ? card : c),
    }));
  }

  function removeCard(cardId) {
    setDashboardResult(prev => ({
      ...prev,
      cards: (prev.cards ?? []).filter(c => c.card_id !== cardId),
      cards_created: Math.max(0, (prev.cards_created ?? 0) - 1),
    }));
  }

  function setDashboardPublished(value) {
    setDashboardResult(prev => ({ ...prev, published: value }));
  }

  function clearDashboardResult() {
    setDashboardResult(null);
  }

  return {
    datasetId,
    uploadResult,
    semantics,
    plan,
    pipelinePlan,
    agentPlan,
    dashboardResult,
    agentResult,
    conflict,
    status,
    errors,
    upload,
    inferSemantics,
    generatePlan,
    createDashboard,
    applyLaunchEvents,
    applyAgentEvents,    
    rehydrate,
    resolveConflict,
    reset,
    addCard,
    replaceCard,
    removeCard,
    setDashboardPublished,
    setAgentResult,
    clearDashboardResult,
  };
}