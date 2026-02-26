import { useRef, useEffect } from "react"

export default function ReadmePanel() {
    const html = props.markdown || ""
    const contentRef = useRef(null)

    // Apply styles after HTML is injected since Tailwind prose classes
    // don't reliably apply in Chainlit CustomElement sandbox
    useEffect(() => {
        const el = contentRef.current
        if (!el) return

        const styles = {
            h1: "font-size:1.125rem;font-weight:700;margin-bottom:0.75rem;",
            h2: "font-size:0.95rem;font-weight:600;margin-bottom:0.5rem;margin-top:1rem;",
            h3: "font-size:0.85rem;font-weight:600;margin-bottom:0.25rem;margin-top:0.75rem;",
            p: "font-size:0.75rem;margin-bottom:0.5rem;opacity:0.8;",
            table: "font-size:0.75rem;width:100%;margin-bottom:0.75rem;border-collapse:collapse;",
            th: "text-align:left;font-weight:600;padding:0.25rem 0.5rem 0.25rem 0;border-bottom:1px solid rgba(255,255,255,0.15);",
            td: "padding:0.25rem 0.5rem 0.25rem 0;border-bottom:1px solid rgba(255,255,255,0.07);",
            code: "font-size:0.7rem;background:rgba(255,255,255,0.08);padding:0.1rem 0.3rem;border-radius:0.25rem;",
            pre: "font-size:0.7rem;background:rgba(255,255,255,0.08);padding:0.5rem;border-radius:0.25rem;margin-bottom:0.5rem;overflow-x:auto;",
            hr: "margin:0.75rem 0;border:none;border-top:1px solid rgba(255,255,255,0.15);",
            ul: "font-size:0.75rem;margin-bottom:0.5rem;padding-left:1rem;list-style:disc;",
            ol: "font-size:0.75rem;margin-bottom:0.5rem;padding-left:1rem;list-style:decimal;",
            li: "margin-bottom:0.15rem;opacity:0.8;",
            strong: "font-weight:600;opacity:1;",
            a: "color:#60a5fa;text-decoration:underline;",
        }

        for (const [tag, style] of Object.entries(styles)) {
            el.querySelectorAll(tag).forEach((node) => {
                node.style.cssText += style
            })
        }

        // pre > code should not have background (pre already has it)
        el.querySelectorAll("pre > code").forEach((node) => {
            node.style.background = "none"
            node.style.padding = "0"
        })
    }, [html])

    return (
        <div className="flex flex-col gap-4 p-2 text-sm">
            <div
                ref={contentRef}
                dangerouslySetInnerHTML={{ __html: html }}
            />
        </div>
    )
}
