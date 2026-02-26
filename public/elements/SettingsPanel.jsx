import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { Filter, Cpu, Database, BookOpen, BrainCircuit } from "lucide-react"

const MENU_ITEMS = [
    { key: "filter", label: "Filters", description: "State & fiscal year filters", icon: Filter },
    { key: "llm", label: "LLM Params", description: "Model, temperature, context window", icon: Cpu },
    { key: "memsql", label: "Knowledge SQL", description: "SQL training data for AI queries", icon: BrainCircuit },
    { key: "mem", label: "Knowledge", description: "Upload & manage KB documents", icon: BookOpen },
    { key: "database", label: "Database", description: "Stats, upload, export, reset", icon: Database },
]

export default function SettingsPanel() {
    const handleOpen = (panel) => {
        callAction({
            name: "open_settings_panel",
            payload: { panel },
        })
    }

    return (
        <div className="flex flex-col gap-2 p-2 text-sm">
            <h3 className="text-sm font-semibold opacity-80 px-1">Settings</h3>
            <Separator />
            {MENU_ITEMS.map((item) => {
                const Icon = item.icon
                return (
                    <button
                        key={item.key}
                        onClick={() => handleOpen(item.key)}
                        className="flex items-center gap-3 w-full text-left py-2.5 px-3 rounded-md hover:bg-muted/60 transition-colors group"
                    >
                        <Icon className="h-4 w-4 opacity-60 group-hover:opacity-100 shrink-0" />
                        <div className="flex flex-col min-w-0">
                            <span className="text-sm font-medium">{item.label}</span>
                            <span className="text-[11px] opacity-50">{item.description}</span>
                        </div>
                    </button>
                )
            })}
        </div>
    )
}
