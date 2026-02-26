import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Input } from "@/components/ui/input"
import { useState, useRef, useEffect } from "react"
import { ArrowLeft, Download, RefreshCw, CheckCircle, XCircle, Loader2, AlertTriangle, FileUp } from "lucide-react"

export default function DatabasePanel() {
    const apiUrl = props.apiUrl || "/api/v1"
    const currentYear = props.currentYear || ""
    const availableYears = props.availableYears || []

    const [loading, setLoading] = useState(true)
    const [health, setHealth] = useState(null)
    const [stats, setStats] = useState(null)
    const [activeJobs, setActiveJobs] = useState([])
    const [statusMsg, setStatusMsg] = useState(null)
    const [confirmAction, setConfirmAction] = useState(null)

    // Export state
    const [exportYear, setExportYear] = useState("")
    const [exportTables, setExportTables] = useState("")
    const [exporting, setExporting] = useState(false)

    // File list state (for upload refresh)
    const [files, setFiles] = useState([])

    // Upload CSV state
    const [uploading, setUploading] = useState(false)
    const csvFileRef = useRef(null)

    // Reset state
    const [resetting, setResetting] = useState(false)

    const showStatus = (type, text) => {
        setStatusMsg({ type, text })
        setTimeout(() => setStatusMsg(null), 5000)
    }

    // Inline confirmation component
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

    const fetchData = async () => {
        setLoading(true)
        try {
            const [healthRes, statsRes, jobsRes, filesRes] = await Promise.all([
                fetch(apiUrl + "/data/health").then(r => r.json()).catch(() => null),
                fetch(apiUrl + "/data/stats").then(r => r.json()).catch(() => null),
                fetch(apiUrl + "/data/load/jobs?active_only=true").then(r => r.json()).catch(() => null),
                fetch(apiUrl + "/data/files").then(r => r.json()).catch(() => null),
            ])
            setHealth(healthRes)
            setStats(statsRes)
            setActiveJobs(jobsRes?.jobs || [])
            setFiles(filesRes?.files || [])
        } catch (e) {
            showStatus("error", "Failed to load database info")
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => { fetchData() }, [])

    // Poll active jobs every 3s when any exist
    useEffect(() => {
        if (activeJobs.length === 0) return
        const interval = setInterval(async () => {
            try {
                const jobsRes = await fetch(apiUrl + "/data/load/jobs?active_only=true").then(r => r.json()).catch(() => null)
                const jobs = jobsRes?.jobs || []
                setActiveJobs(jobs)
                if (jobs.length === 0) {
                    clearInterval(interval)
                    // Refresh all data when jobs finish
                    fetchData()
                }
            } catch (e) { /* ignore polling errors */ }
        }, 3000)
        return () => clearInterval(interval)
    }, [activeJobs.length > 0])

    const handleUploadCsv = async () => {
        const input = csvFileRef.current
        if (!input || !input.files || !input.files.length) {
            showStatus("error", "Select a CSV file first")
            return
        }
        setUploading(true)
        try {
            const fd = new FormData()
            fd.append("file", input.files[0])
            const res = await fetch(apiUrl + "/data/upload", { method: "POST", body: fd })
            if (!res.ok) throw new Error("HTTP " + res.status)
            const data = await res.json()
            const fileInfo = data.file || {}
            showStatus("success", `Uploaded: ${fileInfo.filename || input.files[0].name}`)
            input.value = ""
            // Refresh file list
            const filesRes = await fetch(apiUrl + "/data/files").then(r => r.json()).catch(() => null)
            setFiles(filesRes?.files || [])
        } catch (e) {
            showStatus("error", "Upload failed: " + e.message)
        } finally {
            setUploading(false)
        }
    }

    const handleResetDatabase = () => {
        setConfirmAction({
            location: "reset-db",
            label: "Reset database? This will delete ALL data (households, members, QC errors, load history). Cannot be undone.",
            onConfirm: async () => {
                setConfirmAction(null)
                setResetting(true)
                try {
                    const res = await fetch(apiUrl + "/data/reset", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ confirm: true })
                    })
                    if (!res.ok) throw new Error("HTTP " + res.status)
                    const data = await res.json()
                    showStatus("success", data.message || "Database reset complete")
                    await fetchData()
                } catch (e) {
                    showStatus("error", "Reset failed: " + e.message)
                } finally {
                    setResetting(false)
                }
            }
        })
    }

    const handleExport = async () => {
        setExporting(true)
        try {
            const params = new URLSearchParams()
            if (exportYear) params.set("fiscal_year", exportYear)
            if (exportTables.trim()) params.set("tables", exportTables.trim())
            const qs = params.toString() ? "?" + params.toString() : ""
            const res = await fetch(apiUrl + "/data/export/excel" + qs)
            if (!res.ok) throw new Error("HTTP " + res.status)
            const blob = await res.blob()
            const url = URL.createObjectURL(blob)
            const a = document.createElement("a")
            const ts = new Date().toISOString().replace(/[:.]/g, "").slice(0, 15)
            a.href = url
            a.download = `snapanalyst_export_${ts}.xlsx`
            document.body.appendChild(a)
            a.click()
            document.body.removeChild(a)
            URL.revokeObjectURL(url)
            showStatus("success", "Export downloaded")
        } catch (e) {
            showStatus("error", "Export failed: " + e.message)
        } finally {
            setExporting(false)
        }
    }

    const handleBack = () => {
        callAction({
            name: "open_settings_panel",
            payload: { panel: "settings" },
        })
    }

    const db = health?.database || {}
    const connected = db.connected
    const summary = stats?.summary || {}
    const fiscalYears = summary.fiscal_years || []

    return (
        <div className="flex flex-col gap-4 p-2 text-sm">
            {/* Back button */}
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

            {loading ? (
                <div className="flex items-center justify-center py-8 opacity-50">
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    Loading...
                </div>
            ) : (
                <>
                    {/* Connection Status */}
                    <div>
                        <div className="flex items-center justify-between">
                            <h3 className="text-sm font-semibold opacity-80">Database</h3>
                            <Badge variant="outline" className={`text-[10px] px-1 py-0 ${
                                connected ? "text-green-500 border-green-500" : "text-red-500 border-red-500"
                            }`}>
                                {connected ? "Connected" : "Disconnected"}
                            </Badge>
                        </div>
                        <div className="text-xs opacity-50 mt-1">{db.name || "snapanalyst_db"}</div>
                    </div>

                    <Separator />

                    {/* SNAP Stats */}
                    <div>
                        <h3 className="text-sm font-semibold mb-2 opacity-80">SNAP Data Summary</h3>
                        <div className="grid grid-cols-2 gap-y-1 text-xs">
                            <span>Fiscal Years</span>
                            <span className="text-right font-medium tabular-nums">
                                {fiscalYears.length > 0 ? fiscalYears.join(", ") : "None"}
                            </span>
                            <span>Households</span>
                            <span className="text-right font-medium tabular-nums">{(summary.total_households || 0).toLocaleString()}</span>
                            <span>Members</span>
                            <span className="text-right font-medium tabular-nums">{(summary.total_members || 0).toLocaleString()}</span>
                            <span>QC Errors</span>
                            <span className="text-right font-medium tabular-nums">{(summary.total_qc_errors || 0).toLocaleString()}</span>
                        </div>
                        {stats?.last_load && (
                            <div className="text-[10px] opacity-50 mt-2">Last load: {stats.last_load}</div>
                        )}
                    </div>

                    {/* Active Jobs */}
                    {activeJobs.length > 0 && (
                        <>
                            <Separator />
                            <div>
                                <h3 className="text-sm font-semibold mb-1 opacity-80">Active Jobs</h3>
                                {activeJobs.map((job, i) => {
                                    const progress = job.progress || {}
                                    return (
                                        <div key={i} className="text-xs p-2 bg-blue-500/10 rounded mb-1">
                                            <div className="flex justify-between">
                                                <span className="font-medium">{job.job_id}</span>
                                                <span className="opacity-70">{job.status}</span>
                                            </div>
                                            {progress.percent_complete != null && (
                                                <div className="mt-1">
                                                    <div className="h-1.5 bg-muted rounded overflow-hidden">
                                                        <div
                                                            className="h-full bg-blue-500 rounded transition-all"
                                                            style={{ width: `${progress.percent_complete}%` }}
                                                        />
                                                    </div>
                                                    <div className="text-[10px] opacity-50 mt-0.5">
                                                        {progress.percent_complete?.toFixed(1)}% ({(progress.rows_processed || 0).toLocaleString()} / {(progress.total_rows || 0).toLocaleString()} rows)
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    )
                                })}
                            </div>
                        </>
                    )}

                    <Separator />

                    {/* Upload CSV */}
                    <div>
                        <h3 className="text-sm font-semibold mb-2 opacity-80">Upload CSV</h3>
                        <input type="file" ref={csvFileRef} accept=".csv" className="block w-full text-xs mb-2" />
                        <Button size="sm" className="w-full" onClick={handleUploadCsv} disabled={uploading}>
                            <FileUp className="h-3 w-3 mr-1" />
                            {uploading ? "Uploading..." : "Upload"}
                        </Button>
                        <p className="text-[10px] opacity-40 mt-0.5">Include fiscal year in filename (e.g., qc_pub_fy2023.csv)</p>
                    </div>

                    <Separator />

                    {/* Export */}
                    <div>
                        <h3 className="text-sm font-semibold mb-2 opacity-80">Data Export</h3>

                        {/* Year selector */}
                        <div className="mb-2">
                            <label className="text-xs font-medium opacity-70 mb-1 block">Fiscal Year</label>
                            <select
                                value={exportYear}
                                onChange={(e) => setExportYear(e.target.value)}
                                className="w-full h-8 text-xs rounded border border-border bg-background px-2 focus:outline-none focus:ring-1 focus:ring-ring"
                            >
                                <option value="">All Years</option>
                                {(availableYears.length > 0 ? availableYears : fiscalYears).map((y) => (
                                    <option key={y} value={y}>{y}</option>
                                ))}
                            </select>
                        </div>

                        {/* Tables input */}
                        <div className="mb-2">
                            <label className="text-xs font-medium opacity-70 mb-1 block">Tables (optional)</label>
                            <Input
                                className="h-7 text-xs"
                                value={exportTables}
                                onChange={(e) => setExportTables(e.target.value)}
                                placeholder="e.g. households,snap_my_table"
                            />
                            <p className="text-[10px] opacity-40 mt-0.5">Comma-separated. Leave empty for default tables.</p>
                        </div>

                        <Button size="sm" className="w-full" onClick={handleExport} disabled={exporting}>
                            <Download className="h-3 w-3 mr-1" />
                            {exporting ? "Downloading..." : "Download Excel"}
                        </Button>
                    </div>

                    <Separator />

                    {/* Reset Database */}
                    <div>
                        <h3 className="text-sm font-semibold mb-2 opacity-80">Reset Database</h3>
                        <Button
                            variant="outline"
                            size="sm"
                            className="w-full border-red-400 text-red-400 hover:bg-red-500/10"
                            onClick={handleResetDatabase}
                            disabled={resetting}
                        >
                            <RefreshCw className="h-3 w-3 mr-1" />
                            {resetting ? "Resetting..." : "Reset Database"}
                        </Button>
                        <ConfirmInline location="reset-db" />
                    </div>

                    {/* Custom Data */}
                    {summary.custom_tables > 0 && (
                        <>
                            <Separator />
                            <div>
                                <h3 className="text-sm font-semibold mb-2 opacity-80">Custom Data Summary</h3>
                                <div className="grid grid-cols-2 gap-y-1 text-xs">
                                    <span>Custom Tables</span>
                                    <span className="text-right font-medium tabular-nums">{summary.custom_tables}</span>
                                </div>
                            </div>
                        </>
                    )}

                    {/* Refresh */}
                    <Button variant="outline" size="sm" className="w-full text-muted-foreground" onClick={fetchData}>
                        <RefreshCw className="h-3 w-3 mr-1" />
                        Refresh
                    </Button>
                </>
            )}
        </div>
    )
}
