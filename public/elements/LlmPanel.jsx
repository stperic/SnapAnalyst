import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Input } from "@/components/ui/input"
import { useState, useEffect, useRef } from "react"
import { ArrowLeft, CheckCircle, XCircle, FlaskConical, RotateCcw, ChevronDown, ChevronRight, FileText, Upload, RefreshCw, AlertTriangle } from "lucide-react"

const TABS = [
    { key: "data_query", label: "Data Query" },
    { key: "insights", label: "Insights" },
    { key: "knowledge", label: "Knowledge" },
]

const DEFAULT_SETTINGS = {
    model: "",
    temperature: 0.7,
    max_tokens: 4096,
    top_p: 1.0,
    context_window: null,
}

const DEFAULT_SUMMARY_SETTINGS = {
    model: "",
    temperature: 0.5,
    max_tokens: 4096,
    top_p: 1.0,
    context_window: null,
    summary_enabled: true,
    summary_max_rows: 50,
}

// Prompt type mapping for API calls
const PROMPT_TYPE_MAP = {
    sql: "sql",
    summary: "summary",
    insights: "kb",
    knowledge: "kb",
}

export default function LlmPanel() {
    const apiUrl = props.apiUrl || "/api/v1"
    const userId = props.userId || "default"
    const initialSettings = props.settings || {}
    const initialDefaults = props.defaults || {}

    // Per-mode settings state (sql + summary are separate but shown in "Data Query" tab)
    const [settings, setSettings] = useState({
        sql: { ...DEFAULT_SETTINGS, ...initialSettings.sql },
        summary: { ...DEFAULT_SUMMARY_SETTINGS, ...initialSettings.summary },
        insights: { ...DEFAULT_SETTINGS, ...initialSettings.insights },
        knowledge: { ...DEFAULT_SETTINGS, ...initialSettings.knowledge },
    })

    // Store config defaults for reset
    const [defaults] = useState({
        sql: { ...DEFAULT_SETTINGS, ...initialDefaults.sql },
        summary: { ...DEFAULT_SUMMARY_SETTINGS, ...initialDefaults.summary },
        insights: { ...DEFAULT_SETTINGS, ...initialDefaults.insights },
        knowledge: { ...DEFAULT_SETTINGS, ...initialDefaults.knowledge },
    })

    const [activeTab, setActiveTab] = useState("data_query")
    const [testing, setTesting] = useState(false)
    const [statusMsg, setStatusMsg] = useState(null)
    const [modelStatus, setModelStatus] = useState({ sql: null, summary: null, insights: null, knowledge: null })
    const [dirty, setDirty] = useState({ data_query: false, insights: false, knowledge: false })

    // Prompt state per type
    const [prompts, setPrompts] = useState({})  // { sql: {prompt_text, is_custom, char_count}, summary: {...}, ... }
    const [promptOpen, setPromptOpen] = useState({})
    const [promptExpanded, setPromptExpanded] = useState({})
    const [updatingPrompt, setUpdatingPrompt] = useState({})
    const [confirmAction, setConfirmAction] = useState(null)
    const promptFileRefs = { sql: useRef(null), summary: useRef(null), insights: useRef(null), knowledge: useRef(null) }

    const showStatus = (type, text) => {
        setStatusMsg({ type, text })
        setTimeout(() => setStatusMsg(null), 5000)
    }

    const updateField = (mode, field, value) => {
        setSettings((prev) => ({
            ...prev,
            [mode]: { ...prev[mode], [field]: value },
        }))
        // Map mode to tab dirty flag
        const dirtyKey = (mode === "sql" || mode === "summary") ? "data_query" : mode
        setDirty((prev) => ({ ...prev, [dirtyKey]: true }))
    }

    // --- Prompt management ---
    const fetchPrompt = async (promptType) => {
        try {
            const res = await fetch(apiUrl + "/llm/prompt/" + promptType, {
                headers: { "X-User-ID": userId }
            })
            if (res.ok) {
                const data = await res.json()
                setPrompts((prev) => ({ ...prev, [promptType]: data }))
            }
        } catch (e) {
            // Silently fail
        }
    }

    useEffect(() => {
        // Fetch all prompt types on mount
        for (const pt of ["sql", "summary", "kb"]) {
            fetchPrompt(pt)
        }
    }, [])

    const handlePromptUpload = async (promptType) => {
        const ref = promptFileRefs[promptType]
        const input = ref?.current
        if (!input || !input.files || !input.files.length) {
            showStatus("error", "Select a .txt file for the prompt")
            return
        }
        const file = input.files[0]
        if (!file.name.endsWith(".txt")) {
            showStatus("error", "Only .txt files are allowed for prompts")
            return
        }

        const apiType = promptType === "insights" || promptType === "knowledge" ? "kb" : promptType
        const label = { sql: "SQL generation", summary: "Results summary", kb: "KB insight" }[apiType]

        setConfirmAction({
            location: "prompt:" + promptType,
            label: `Update ${label} prompt with this file?`,
            onConfirm: async () => {
                setConfirmAction(null)
                setUpdatingPrompt((prev) => ({ ...prev, [promptType]: true }))
                try {
                    const text = await file.text()
                    const res = await fetch(apiUrl + "/llm/prompt/" + apiType, {
                        method: "PUT",
                        headers: { "Content-Type": "application/json", "X-User-ID": userId },
                        body: JSON.stringify({ prompt_text: text })
                    })
                    if (!res.ok) {
                        const err = await res.json().catch(() => ({}))
                        throw new Error(err.detail || "HTTP " + res.status)
                    }
                    showStatus("success", `${label} prompt updated`)
                    input.value = ""
                    await fetchPrompt(apiType)
                } catch (e) {
                    showStatus("error", "Prompt update failed: " + e.message)
                } finally {
                    setUpdatingPrompt((prev) => ({ ...prev, [promptType]: false }))
                }
            }
        })
    }

    const handlePromptReset = async (promptType) => {
        const apiType = promptType === "insights" || promptType === "knowledge" ? "kb" : promptType
        const label = { sql: "SQL generation", summary: "Results summary", kb: "KB insight" }[apiType]

        setConfirmAction({
            location: "prompt:" + promptType,
            label: `Reset ${label} prompt to system default?`,
            onConfirm: async () => {
                setConfirmAction(null)
                setUpdatingPrompt((prev) => ({ ...prev, [promptType]: true }))
                try {
                    const res = await fetch(apiUrl + "/llm/prompt/" + apiType, {
                        method: "DELETE",
                        headers: { "X-User-ID": userId }
                    })
                    if (!res.ok) throw new Error("HTTP " + res.status)
                    showStatus("success", `${label} prompt reset to default`)
                    await fetchPrompt(apiType)
                } catch (e) {
                    showStatus("error", "Prompt reset failed: " + e.message)
                } finally {
                    setUpdatingPrompt((prev) => ({ ...prev, [promptType]: false }))
                }
            }
        })
    }

    // Inline confirmation
    const ConfirmInline = ({ location }) => {
        if (!confirmAction || confirmAction.location !== location) return null
        return (
            <div className="p-2 rounded bg-yellow-500/15 border border-yellow-500/30 mt-1">
                <div className="flex items-start gap-2 text-xs mb-2">
                    <AlertTriangle className="h-3 w-3 shrink-0 text-yellow-500 mt-0.5" />
                    <span>{confirmAction.label}</span>
                </div>
                <div className="flex gap-2">
                    <Button size="sm" variant="outline" className="h-6 text-xs border-red-400 text-red-400 hover:bg-red-500/10" onClick={confirmAction.onConfirm}>
                        Yes, proceed
                    </Button>
                    <Button size="sm" variant="outline" className="h-6 text-xs" onClick={() => setConfirmAction(null)}>
                        Cancel
                    </Button>
                </div>
            </div>
        )
    }

    // --- Prompt section component ---
    const PromptSection = ({ promptType, label }) => {
        const apiType = promptType === "insights" || promptType === "knowledge" ? "kb" : promptType
        const data = prompts[apiType]
        const isOpen = promptOpen[promptType]
        const isExpanded = promptExpanded[promptType]
        const isUpdating = updatingPrompt[promptType]
        const fileRef = promptFileRefs[promptType]

        return (
            <div>
                <button onClick={() => setPromptOpen((prev) => ({ ...prev, [promptType]: !prev[promptType] }))}
                    className="flex items-center gap-1 w-full text-left py-1 px-1 rounded hover:bg-muted/50 text-xs font-medium">
                    {isOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                    <FileText className="h-3 w-3" />
                    System Prompt
                    {data && (
                        <Badge variant="outline" className={`ml-auto text-[10px] px-1 py-0 ${
                            data.is_custom ? "text-blue-500 border-blue-500" : "text-gray-400 border-gray-500"
                        }`}>
                            {data.is_custom ? "Custom" : "Default"}
                        </Badge>
                    )}
                </button>
                {isOpen && data && (
                    <div className="ml-2 mt-1 space-y-2">
                        <div className="grid grid-cols-2 gap-y-1 text-xs">
                            <span>Type</span><span className="text-right">{label}</span>
                            <span>Characters</span><span className="text-right font-medium tabular-nums">{data.char_count?.toLocaleString()}</span>
                        </div>
                        <div>
                            <pre className="text-[10px] bg-muted/50 rounded p-2 whitespace-pre-wrap break-words max-h-40 overflow-y-auto">
                                {isExpanded ? data.prompt_text : (data.prompt_text || "").slice(0, 500)}
                            </pre>
                            {data.prompt_text && data.prompt_text.length > 500 && (
                                <button onClick={() => setPromptExpanded((prev) => ({ ...prev, [promptType]: !prev[promptType] }))}
                                    className="text-[10px] text-blue-400 hover:text-blue-300 mt-1">
                                    {isExpanded ? "Show less" : "Show more..."}
                                </button>
                            )}
                        </div>
                        <div>
                            <input type="file" ref={fileRef} accept=".txt" className="block w-full text-xs mb-1" />
                            <Button size="sm" className="w-full" onClick={() => handlePromptUpload(promptType)} disabled={isUpdating}>
                                <Upload className="h-3 w-3 mr-1" />
                                {isUpdating ? "Updating..." : "Upload Prompt"}
                            </Button>
                        </div>
                        {data.is_custom && (
                            <Button variant="outline" size="sm" className="w-full border-red-400 text-red-400 hover:bg-red-500/10"
                                onClick={() => handlePromptReset(promptType)} disabled={isUpdating}>
                                <RefreshCw className="h-3 w-3 mr-1" />
                                Reset to Default
                            </Button>
                        )}
                        <ConfirmInline location={"prompt:" + promptType} />
                    </div>
                )}
            </div>
        )
    }

    // --- Apply / Reset ---
    const handleApply = async (tabKey) => {
        if (tabKey === "data_query") {
            // Apply both sql and summary
            for (const mode of ["sql", "summary"]) {
                const s = settings[mode]
                const model = s.model
                if (model && modelStatus[mode] !== "ok") {
                    await _testAndApply(mode, s)
                } else {
                    callAction({ name: "llm_settings_changed", payload: { mode, settings: s } })
                }
            }
            setDirty((prev) => ({ ...prev, data_query: false }))
            showStatus("success", "Data Query settings applied")
        } else {
            const mode = tabKey
            const s = settings[mode]
            const model = s.model
            if (model && modelStatus[mode] !== "ok") {
                await _testAndApply(mode, s)
            } else {
                callAction({ name: "llm_settings_changed", payload: { mode, settings: s } })
            }
            setDirty((prev) => ({ ...prev, [mode]: false }))
            if (modelStatus[mode] !== "fail") {
                showStatus("success", `${TABS.find((t) => t.key === tabKey)?.label} settings applied`)
            }
        }
    }

    const _testAndApply = async (mode, s) => {
        const model = s.model
        setTesting(true)
        try {
            const res = await fetch(apiUrl + "/llm/model-test", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ model }),
            })
            const data = await res.json()
            if (res.ok && data.success) {
                setModelStatus((prev) => ({ ...prev, [mode]: "ok" }))
            } else {
                setModelStatus((prev) => ({ ...prev, [mode]: "fail" }))
                showStatus("error", `Model "${model}" not available — settings saved anyway`)
            }
        } catch (e) {
            setModelStatus((prev) => ({ ...prev, [mode]: "fail" }))
            showStatus("error", `Model test failed — settings saved anyway`)
        } finally {
            setTesting(false)
        }
        callAction({ name: "llm_settings_changed", payload: { mode, settings: s } })
    }

    const handleReset = (tabKey) => {
        if (tabKey === "data_query") {
            setSettings((prev) => ({
                ...prev,
                sql: { ...defaults.sql },
                summary: { ...defaults.summary },
            }))
            setDirty((prev) => ({ ...prev, data_query: true }))
            showStatus("info", "Data Query settings reset to defaults (click Apply to save)")
        } else {
            setSettings((prev) => ({
                ...prev,
                [tabKey]: { ...defaults[tabKey] },
            }))
            setDirty((prev) => ({ ...prev, [tabKey]: true }))
            showStatus("info", `${TABS.find((t) => t.key === tabKey)?.label} settings reset to defaults (click Apply to save)`)
        }
    }

    const handleTestModel = async (mode) => {
        setTesting(true)
        setModelStatus((prev) => ({ ...prev, [mode]: null }))
        try {
            const model = settings[mode].model
            if (!model) {
                showStatus("error", "No model name specified")
                return
            }
            const res = await fetch(apiUrl + "/llm/model-test", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ model }),
            })
            const data = await res.json()
            if (res.ok && data.success) {
                setModelStatus((prev) => ({ ...prev, [mode]: "ok" }))
                showStatus("success", `Model "${model}" is available`)
            } else {
                setModelStatus((prev) => ({ ...prev, [mode]: "fail" }))
                showStatus("error", data.message || data.detail || data.error || `Model "${model}" test failed`)
            }
        } catch (e) {
            setModelStatus((prev) => ({ ...prev, [mode]: "fail" }))
            showStatus("error", "Model test failed: " + e.message)
        } finally {
            setTesting(false)
        }
    }

    // Debounced context window lookup
    const debounceRef = useRef(null)
    // For data_query tab, track both sql and summary models
    const activeMode = activeTab === "data_query" ? "sql" : activeTab
    const currentModel = settings[activeMode]?.model || ""

    useEffect(() => {
        if (debounceRef.current) clearTimeout(debounceRef.current)
        if (!currentModel) {
            setSettings((prev) => ({
                ...prev,
                [activeMode]: { ...prev[activeMode], context_window: null },
            }))
            return
        }
        debounceRef.current = setTimeout(async () => {
            try {
                const res = await fetch(apiUrl + "/llm/model-info/" + encodeURIComponent(currentModel))
                if (res.ok) {
                    const data = await res.json()
                    setSettings((prev) => ({
                        ...prev,
                        [activeMode]: {
                            ...prev[activeMode],
                            context_window: data.found && data.context_window ? data.context_window : null,
                        },
                    }))
                }
            } catch (e) {
                // Silently fail
            }
        }, 400)
        return () => clearTimeout(debounceRef.current)
    }, [currentModel, activeMode])

    // Also do context window lookup for summary model
    const summaryModel = settings.summary?.model || ""
    const summaryDebounceRef = useRef(null)
    useEffect(() => {
        if (activeTab !== "data_query") return
        if (summaryDebounceRef.current) clearTimeout(summaryDebounceRef.current)
        if (!summaryModel) {
            setSettings((prev) => ({
                ...prev,
                summary: { ...prev.summary, context_window: null },
            }))
            return
        }
        summaryDebounceRef.current = setTimeout(async () => {
            try {
                const res = await fetch(apiUrl + "/llm/model-info/" + encodeURIComponent(summaryModel))
                if (res.ok) {
                    const data = await res.json()
                    setSettings((prev) => ({
                        ...prev,
                        summary: {
                            ...prev.summary,
                            context_window: data.found && data.context_window ? data.context_window : null,
                        },
                    }))
                }
            } catch (e) { }
        }, 400)
        return () => clearTimeout(summaryDebounceRef.current)
    }, [summaryModel, activeTab])

    // --- Model + settings fields component ---
    const ModelSettingsFields = ({ mode, tempMax, showTopP }) => {
        const current = settings[mode]
        return (
            <div className="space-y-3">
                {/* Model */}
                <div>
                    <div className="flex items-center justify-between mb-1">
                        <label className="text-xs font-medium opacity-70">Model</label>
                        {modelStatus[mode] === "ok" && (
                            <span className="flex items-center gap-1 text-[10px] text-green-500 font-medium">
                                <CheckCircle className="h-3.5 w-3.5" fill="currentColor" stroke="white" strokeWidth={2.5} /> Connected
                            </span>
                        )}
                        {modelStatus[mode] === "fail" && (
                            <span className="flex items-center gap-1 text-[10px] text-red-500 font-medium">
                                <XCircle className="h-3.5 w-3.5" fill="currentColor" stroke="white" strokeWidth={2.5} /> Failed
                            </span>
                        )}
                    </div>
                    <div className="flex gap-1.5">
                        <Input
                            className="h-7 text-xs flex-1"
                            value={current.model}
                            onChange={(e) => {
                                updateField(mode, "model", e.target.value)
                                setModelStatus((prev) => ({ ...prev, [mode]: null }))
                            }}
                            placeholder="e.g. gpt-4o, claude-sonnet-4-20250514"
                        />
                        <button
                            onClick={() => handleTestModel(mode)}
                            disabled={testing || !current.model}
                            className="h-7 px-2 rounded border border-border text-[10px] font-medium hover:bg-muted transition-colors disabled:opacity-40 shrink-0"
                            title="Test connection"
                        >
                            {testing ? "..." : <FlaskConical className="h-3 w-3" />}
                        </button>
                    </div>
                    <div className="text-[10px] tabular-nums opacity-50 mt-1">
                        {current.context_window
                            ? `Context: ${current.context_window.toLocaleString()} tokens`
                            : current.model ? "Context: unknown" : ""}
                    </div>
                </div>

                {/* Temperature */}
                <div>
                    <div className="flex items-center justify-between mb-1">
                        <label className="text-xs font-medium opacity-70">Temperature</label>
                        <span className="text-xs font-mono tabular-nums">{(current.temperature ?? 0.1).toFixed(1)}</span>
                    </div>
                    <input
                        type="range"
                        min="0"
                        max={tempMax || "2"}
                        step="0.1"
                        value={current.temperature ?? 0.1}
                        onChange={(e) => updateField(mode, "temperature", parseFloat(e.target.value))}
                        className="w-full h-1.5 accent-primary"
                    />
                    <div className="flex justify-between text-[10px] opacity-40 mt-0.5">
                        <span>Precise</span>
                        {tempMax !== "0.2" && <span>Creative</span>}
                    </div>
                </div>

                {/* Max Tokens */}
                <div>
                    <label className="text-xs font-medium opacity-70 mb-1 block">Max Tokens</label>
                    <Input
                        type="number"
                        className="h-7 text-xs"
                        value={current.max_tokens ?? ""}
                        onChange={(e) => updateField(mode, "max_tokens", parseInt(e.target.value) || 0)}
                        min={0}
                    />
                </div>

                {/* Top P */}
                {showTopP !== false && (
                    <div>
                        <div className="flex items-center justify-between mb-1">
                            <label className="text-xs font-medium opacity-70">Top P</label>
                            <span className="text-xs font-mono tabular-nums">{(current.top_p ?? 1.0).toFixed(2)}</span>
                        </div>
                        {mode === "sql" ? (
                            <div className="text-[10px] opacity-40">Fixed for SQL accuracy</div>
                        ) : (
                            <input
                                type="range"
                                min="0"
                                max="1"
                                step="0.05"
                                value={current.top_p ?? 1.0}
                                onChange={(e) => updateField(mode, "top_p", parseFloat(e.target.value))}
                                className="w-full h-1.5 accent-primary"
                            />
                        )}
                    </div>
                )}
            </div>
        )
    }

    const handleBack = () => {
        callAction({
            name: "open_settings_panel",
            payload: { panel: "settings" },
        })
    }

    // --- Render ---
    const current = activeTab === "data_query" ? settings.sql : settings[activeTab]

    return (
        <div className="flex flex-col gap-4 p-2 text-sm">
            {/* Back to Settings */}
            <button
                onClick={handleBack}
                className="flex items-center gap-1 text-xs opacity-60 hover:opacity-100 transition-opacity w-fit"
            >
                <ArrowLeft className="h-3 w-3" />
                Settings
            </button>

            {/* Tabs */}
            <div className="flex gap-1">
                {TABS.map((tab) => (
                    <button
                        key={tab.key}
                        onClick={() => setActiveTab(tab.key)}
                        className={`flex-1 text-xs py-1.5 px-2 rounded font-medium transition-colors ${activeTab === tab.key
                                ? "bg-primary text-primary-foreground"
                                : "bg-muted/50 hover:bg-muted text-muted-foreground"
                            }`}
                    >
                        {tab.label}
                        {dirty[tab.key] && <span className="ml-1 text-yellow-400">*</span>}
                    </button>
                ))}
            </div>

            <Separator />

            {/* Provider (read-only) */}
            {props.provider && (
                <div className="text-xs opacity-50">
                    Provider: <span className="font-medium opacity-80">{props.provider}</span>
                </div>
            )}

            {/* === DATA QUERY TAB === */}
            {activeTab === "data_query" && (
                <div className="space-y-4">
                    {/* SQL Query section */}
                    <div>
                        <h3 className="text-xs font-semibold opacity-80 mb-3 uppercase tracking-wide">SQL Query</h3>
                        <ModelSettingsFields mode="sql" tempMax="0.2" showTopP={true} />
                    </div>

                    {/* SQL Prompt */}
                    <PromptSection promptType="sql" label="SQL Generation" />

                    <Separator />

                    {/* Results Summary section */}
                    <div>
                        <h3 className="text-xs font-semibold opacity-80 mb-3 uppercase tracking-wide">Results Summary</h3>

                        {/* Summary toggle */}
                        <div className="mb-3">
                            <div className="flex rounded border border-border overflow-hidden">
                                <button
                                    onClick={() => updateField("summary", "summary_enabled", false)}
                                    className={`flex-1 text-[11px] py-1.5 font-medium transition-colors ${!settings.summary.summary_enabled
                                            ? "bg-primary text-primary-foreground"
                                            : "bg-transparent text-muted-foreground hover:bg-muted/50"
                                        }`}
                                >
                                    Template
                                </button>
                                <button
                                    onClick={() => updateField("summary", "summary_enabled", true)}
                                    className={`flex-1 text-[11px] py-1.5 font-medium transition-colors border-l border-border ${settings.summary.summary_enabled
                                            ? "bg-primary text-primary-foreground"
                                            : "bg-transparent text-muted-foreground hover:bg-muted/50"
                                        }`}
                                >
                                    AI Summary
                                </button>
                            </div>
                            <p className="text-[10px] opacity-40 mt-1">
                                {settings.summary.summary_enabled
                                    ? "LLM analyzes results with natural language"
                                    : "Basic summaries (e.g., \"Found 42 results.\")"}
                            </p>
                        </div>

                        {settings.summary.summary_enabled && (
                            <>
                                <ModelSettingsFields mode="summary" tempMax="2" showTopP={false} />

                                {/* Summary Max Rows */}
                                <div className="mt-3">
                                    <label className="text-xs font-medium opacity-70 mb-1 block">Summary Max Rows</label>
                                    <Input
                                        type="number"
                                        className="h-7 text-xs"
                                        value={settings.summary.summary_max_rows ?? 50}
                                        onChange={(e) => updateField("summary", "summary_max_rows", parseInt(e.target.value) || 10)}
                                        min={1}
                                        max={500}
                                    />
                                    <p className="text-[10px] opacity-40 mt-0.5">
                                        Max data rows sent to LLM (scales with context)
                                    </p>
                                </div>

                                {/* Summary Prompt */}
                                <div className="mt-3">
                                    <PromptSection promptType="summary" label="Results Summary" />
                                </div>
                            </>
                        )}
                    </div>
                </div>
            )}

            {/* === INSIGHTS TAB === */}
            {activeTab === "insights" && (
                <div className="space-y-4">
                    <ModelSettingsFields mode="insights" tempMax="2" showTopP={true} />
                    <PromptSection promptType="insights" label="KB Insight" />
                </div>
            )}

            {/* === KNOWLEDGE TAB === */}
            {activeTab === "knowledge" && (
                <div className="space-y-4">
                    <ModelSettingsFields mode="knowledge" tempMax="2" showTopP={true} />
                    <PromptSection promptType="knowledge" label="KB Insight" />
                </div>
            )}

            <Separator />

            {/* Action Buttons */}
            <div className="space-y-3">
                <Button size="sm" className="w-full" onClick={() => handleApply(activeTab)} disabled={!dirty[activeTab]}>
                    {dirty[activeTab] ? "Apply Changes" : "No Changes"}
                </Button>
                <Button variant="outline" size="sm" className="w-full text-muted-foreground" onClick={() => handleReset(activeTab)}>
                    <RotateCcw className="h-3 w-3 mr-1" />
                    Reset to Defaults
                </Button>
            </div>

            {/* Status message banner */}
            {statusMsg && (
                <div className={`flex items-center gap-2 p-2 rounded text-xs ${statusMsg.type === "success" ? "bg-green-500/15 text-green-400" :
                        statusMsg.type === "error" ? "bg-red-500/15 text-red-400" :
                            "bg-blue-500/15 text-blue-400"
                    }`}>
                    {statusMsg.type === "success" ? <CheckCircle className="h-3 w-3 shrink-0" /> :
                        statusMsg.type === "error" ? <XCircle className="h-3 w-3 shrink-0" /> : null}
                    <span>{statusMsg.text}</span>
                    <button onClick={() => setStatusMsg(null)} className="ml-auto opacity-60 hover:opacity-100">&times;</button>
                </div>
            )}
        </div>
    )
}
