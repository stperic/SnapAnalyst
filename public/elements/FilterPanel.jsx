import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { useState } from "react"
import { ArrowLeft, CheckCircle, XCircle, Filter, RotateCcw } from "lucide-react"

export default function FilterPanel() {
    const apiUrl = props.apiUrl || "/api/v1"
    const [state, setState] = useState(props.currentState || "All States")
    const [year, setYear] = useState(props.currentYear || "All Years")
    const [applying, setApplying] = useState(false)
    const [clearing, setClearing] = useState(false)
    const [statusMsg, setStatusMsg] = useState(null)

    const states = props.states || ["All States"]
    const years = props.years || ["All Years"]

    const isActive = state !== "All States" || year !== "All Years"

    const showStatus = (type, text) => {
        setStatusMsg({ type, text })
        setTimeout(() => setStatusMsg(null), 5000)
    }

    const handleApply = async () => {
        setApplying(true)
        try {
            const stateVal = state === "All States" ? null : state
            const yearVal = year === "All Years" ? null : parseInt(year)
            const res = await fetch(apiUrl + "/filter/set", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ state: stateVal, fiscal_year: yearVal }),
            })
            if (!res.ok) throw new Error("HTTP " + res.status)
            showStatus("success", "Filter applied")
            callAction({
                name: "filter_applied",
                payload: { state: stateVal, fiscal_year: yearVal },
            })
        } catch (e) {
            showStatus("error", "Failed to apply filter: " + e.message)
        } finally {
            setApplying(false)
        }
    }

    const handleClear = async () => {
        setClearing(true)
        try {
            const res = await fetch(apiUrl + "/filter/clear", { method: "POST" })
            if (!res.ok) throw new Error("HTTP " + res.status)
            setState("All States")
            setYear("All Years")
            showStatus("success", "Filter cleared")
            callAction({
                name: "filter_applied",
                payload: { state: null, fiscal_year: null },
            })
        } catch (e) {
            showStatus("error", "Failed to clear filter: " + e.message)
        } finally {
            setClearing(false)
        }
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

            {/* Filter Status */}
            <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold opacity-80">Data Filters</h3>
                <Badge variant="outline" className={`text-[10px] px-1 py-0 ${
                    isActive ? "text-green-500 border-green-500" : "text-gray-400 border-gray-500"
                }`}>
                    {isActive ? "Active" : "Inactive"}
                </Badge>
            </div>

            <Separator />

            {/* State Dropdown */}
            <div>
                <label className="text-xs font-medium opacity-70 mb-1 block">State</label>
                <select
                    value={state}
                    onChange={(e) => setState(e.target.value)}
                    className="w-full h-8 text-xs rounded border border-border bg-background px-2 focus:outline-none focus:ring-1 focus:ring-ring"
                >
                    {states.map((s) => (
                        <option key={s} value={s}>{s}</option>
                    ))}
                </select>
            </div>

            {/* Year Dropdown */}
            <div>
                <label className="text-xs font-medium opacity-70 mb-1 block">Fiscal Year</label>
                <select
                    value={year}
                    onChange={(e) => setYear(e.target.value)}
                    className="w-full h-8 text-xs rounded border border-border bg-background px-2 focus:outline-none focus:ring-1 focus:ring-ring"
                >
                    {years.map((y) => (
                        <option key={y} value={y}>{y}</option>
                    ))}
                </select>
            </div>

            <Separator />

            {/* Action Buttons */}
            <div className="flex gap-2">
                <Button size="sm" className="flex-1" onClick={handleApply} disabled={applying}>
                    <Filter className="h-3 w-3 mr-1" />
                    {applying ? "Applying..." : "Apply"}
                </Button>
                <Button variant="outline" size="sm" className="flex-1" onClick={handleClear} disabled={clearing}>
                    <RotateCcw className="h-3 w-3 mr-1" />
                    {clearing ? "Clearing..." : "Clear"}
                </Button>
            </div>
        </div>
    )
}
