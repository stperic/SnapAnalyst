import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { useState, useRef } from "react"
import { ArrowLeft, Trash2, Upload, RefreshCw, ChevronDown, ChevronRight, AlertTriangle, CheckCircle, XCircle } from "lucide-react"

export default function MemsqlPanel() {
    const [uploading, setUploading] = useState(false)
    const [resetting, setResetting] = useState(false)
    const [reloadTraining, setReloadTraining] = useState(true)
    const [openSections, setOpenSections] = useState({})
    const [statusMsg, setStatusMsg] = useState(null)
    const [confirmAction, setConfirmAction] = useState(null)
    const fileInputRef = useRef(null)

    // API base URL passed from Python (e.g. "http://localhost:8000/api/v1")
    const apiUrl = props.apiUrl || "/api/v1"

    // Local state for data — initialized from props, updated after mutations
    const [stats, setStats] = useState(props.stats || {})
    const [ddlEntries, setDdlEntries] = useState(props.ddl || [])
    const [docEntries, setDocEntries] = useState(props.documentation || [])
    const [sqlEntries, setSqlEntries] = useState(props.sql || [])

    const toggle = (key) => setOpenSections(prev => ({ ...prev, [key]: !prev[key] }))

    const showStatus = (type, text) => {
        setStatusMsg({ type, text })
        setTimeout(() => setStatusMsg(null), 5000)
    }

    // Inline confirmation component — renders at the trigger location
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

    const refreshData = async () => {
        try {
            const [statsRes, listRes] = await Promise.all([
                fetch(apiUrl + "/llm/vanna/stats"),
                fetch(apiUrl + "/llm/vanna/list")
            ])
            const newStats = await statsRes.json()
            const newList = await listRes.json()
            setStats(newStats)
            setDdlEntries(newList.ddl || [])
            setDocEntries(newList.documentation || [])
            setSqlEntries(newList.sql || [])
        } catch (e) {
            showStatus("error", "Failed to refresh: " + e.message)
        }
    }

    const handleDelete = async (id) => {
        setConfirmAction({
            location: "delete:" + id,
            label: "Delete this training entry?",
            onConfirm: async () => {
                setConfirmAction(null)
                try {
                    const res = await fetch(apiUrl + "/llm/vanna/" + encodeURIComponent(id), { method: "DELETE" })
                    if (!res.ok) throw new Error("HTTP " + res.status)
                    showStatus("success", "Entry deleted")
                    await refreshData()
                } catch (e) {
                    showStatus("error", "Delete failed: " + e.message)
                }
            }
        })
    }

    const handleReset = async () => {
        const extra = reloadTraining
            ? " Training data from the training folder will be reloaded."
            : " Training data will NOT be reloaded (add manually via Upload)."
        setConfirmAction({
            location: "reset",
            label: "Reset SQL Training? This will clear ALL training data and rebuild DDL from the database." + extra + " Cannot be undone.",
            onConfirm: async () => {
                setConfirmAction(null)
                setResetting(true)
                try {
                    const res = await fetch(apiUrl + "/llm/vanna/reset", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ reload_training_data: reloadTraining })
                    })
                    const data = await res.json()
                    showStatus("success", data.message || "Reset complete")
                    await refreshData()
                } catch (e) {
                    showStatus("error", "Reset failed: " + e.message)
                } finally {
                    setResetting(false)
                }
            }
        })
    }

    const handleUpload = async () => {
        const input = fileInputRef.current
        if (!input || !input.files || !input.files.length) {
            showStatus("error", "Select at least one file")
            return
        }
        const fd = new FormData()
        for (let i = 0; i < input.files.length; i++) fd.append("files", input.files[i])
        setUploading(true)
        try {
            const res = await fetch(apiUrl + "/llm/vanna/add", { method: "POST", body: fd })
            if (!res.ok) throw new Error("HTTP " + res.status)
            const data = await res.json()
            showStatus("success", data.message || `Added ${data.entries_added || 0} entries`)
            input.value = ""
            await refreshData()
        } catch (e) {
            showStatus("error", "Upload failed: " + e.message)
        } finally {
            setUploading(false)
        }
    }

    const EntryRow = ({ id, label }) => (
        <div>
            <div className="flex items-center justify-between gap-1 py-0.5 px-1 rounded hover:bg-muted/50 group">
                <span className="truncate text-xs">
                    <code className="text-[10px] opacity-50 mr-1">{id.slice(0, 12)}...</code>
                    {label}
                </span>
                <Button variant="ghost" size="icon" className="h-5 w-5 opacity-0 group-hover:opacity-100 text-destructive"
                    onClick={() => handleDelete(id)}>
                    <Trash2 className="h-3 w-3" />
                </Button>
            </div>
            <ConfirmInline location={"delete:" + id} />
        </div>
    )

    const Section = ({ sectionKey, title, count, children }) => (
        <div className="mb-1">
            <button onClick={() => toggle(sectionKey)}
                className="flex items-center gap-1 w-full text-left py-1 px-1 rounded hover:bg-muted/50 text-sm font-medium">
                {openSections[sectionKey] ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                {title} ({count})
            </button>
            {openSections[sectionKey] && <div className="ml-2">{children}</div>}
        </div>
    )

    const extractTableName = (content) => {
        if (!content || !content.includes("CREATE TABLE")) return null
        const parts = content.split("CREATE TABLE")
        if (parts.length > 1) return parts[1].trim().split("(")[0].trim()
        return null
    }

    const handleBack = () => {
        callAction({
            name: "open_settings_panel",
            payload: { panel: "settings" },
        })
    }

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

            {/* Status message banner */}
            {statusMsg && (
                <div className={`flex items-center gap-2 p-2 rounded text-xs ${
                    statusMsg.type === "success" ? "bg-green-500/15 text-green-400" :
                    statusMsg.type === "error" ? "bg-red-500/15 text-red-400" :
                    "bg-blue-500/15 text-blue-400"
                }`}>
                    {statusMsg.type === "success" ? <CheckCircle className="h-3 w-3 shrink-0" /> :
                     statusMsg.type === "error" ? <XCircle className="h-3 w-3 shrink-0" /> : null}
                    <span>{statusMsg.text}</span>
                    <button onClick={() => setStatusMsg(null)} className="ml-auto opacity-60 hover:opacity-100">&times;</button>
                </div>
            )}

            {/* Stats */}
            <div>
                <h3 className="text-sm font-semibold mb-2 opacity-80">Statistics</h3>
                <div className="grid grid-cols-2 gap-y-1 text-xs">
                    <span>DDL (schema)</span><span className="text-right font-medium tabular-nums">{stats.ddl_count || 0}</span>
                    <span>Docs (chunks)</span><span className="text-right font-medium tabular-nums">{stats.documentation_count || 0}</span>
                    <span>SQL Pairs</span><span className="text-right font-medium tabular-nums">{stats.sql_count || 0}</span>
                    <Separator className="col-span-2 my-1" />
                    <span className="font-semibold">Total</span><span className="text-right font-bold tabular-nums">{stats.total_count || 0}</span>
                </div>
            </div>

            <Separator />

            {/* Entries */}
            <div>
                {ddlEntries.length > 0 && (
                    <Section sectionKey="ddl" title="DDL" count={stats.ddl_count || ddlEntries.length}>
                        {ddlEntries.map(e => (
                            <EntryRow key={e.id} id={e.id} label={extractTableName(e.content) || (e.content || "").slice(0, 60) + "..."} />
                        ))}
                    </Section>
                )}
                {docEntries.length > 0 && (
                    <Section sectionKey="doc" title="Documentation" count={stats.documentation_count || docEntries.length}>
                        {docEntries.map(e => (
                            <EntryRow key={e.id} id={e.id} label={(e.content || "").slice(0, 80) + "..."} />
                        ))}
                    </Section>
                )}
                {sqlEntries.length > 0 && (
                    <Section sectionKey="sql" title="SQL Pairs" count={stats.sql_count || sqlEntries.length}>
                        {sqlEntries.map(e => (
                            <EntryRow key={e.id} id={e.id} label={e.question || ""} />
                        ))}
                    </Section>
                )}
            </div>

            <Separator />

            {/* Upload */}
            <div>
                <h3 className="text-sm font-semibold mb-2 opacity-80">Upload Training Data</h3>
                <input type="file" ref={fileInputRef} multiple accept=".md,.txt,.json" className="block w-full text-xs mb-2" />
                <Button size="sm" className="w-full" onClick={handleUpload} disabled={uploading}>
                    <Upload className="h-3 w-3 mr-1" />
                    {uploading ? "Uploading..." : "Upload"}
                </Button>
                <p className="text-[10px] opacity-50 mt-1">.md/.txt → documentation &nbsp; .json → question-SQL pairs</p>
            </div>

            <Separator />

            {/* Actions */}
            <div>
                <h3 className="text-sm font-semibold mb-2 opacity-80">Actions</h3>
                <label className="flex items-center gap-2 text-xs mb-2 cursor-pointer">
                    <input type="checkbox" checked={reloadTraining} onChange={e => setReloadTraining(e.target.checked)}
                        className="rounded border-gray-500" />
                    Reload SNAP training data
                </label>
                <Button variant="outline" size="sm" className="w-full border-red-400 text-red-400 hover:bg-red-500/10" onClick={handleReset} disabled={resetting}>
                    <RefreshCw className="h-3 w-3 mr-1" />
                    {resetting ? "Resetting..." : "Reset"}
                </Button>
                <ConfirmInline location="reset" />
            </div>
        </div>
    )
}
