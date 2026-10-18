import { useMemo, useState, type FormEvent } from "react";
import { createSupportCase, type ProtectedRequestOptions } from "./api";
import type { FrontendAuthContextValue } from "./auth";
import { runtimeConfig } from "./runtimeConfig";

export function BetaFeedback({ auth, route }: { auth: FrontendAuthContextValue; route: string }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const protectedOptions = useMemo<ProtectedRequestOptions>(
    () => ({ getAccessToken: auth.getAccessTokenSilently }),
    [auth.getAccessTokenSilently],
  );

  async function submit(event: FormEvent) {
    event.preventDefault();
    const comment = text.trim();
    if (!comment) return;
    setStatus("sending");
    try {
      await createSupportCase({
        case_type: "product_issue",
        title: `Beta feedback: ${route}`.slice(0, 255),
        description: `${comment}\n\nRoute: ${route}\nRelease: ${runtimeConfig.releaseId}`,
        subject_type: "product_surface",
        subject_id: route.slice(0, 128),
        priority: "normal",
      }, protectedOptions);
      setText("");
      setStatus("sent");
    } catch {
      setStatus("error");
    }
  }

  return (
    <aside className="beta-feedback">
      <button onClick={() => { setOpen((value) => !value); setStatus("idle"); }} type="button">
        Feedback
      </button>
      {open ? (
        <form onSubmit={submit}>
          <label htmlFor="beta-feedback-text">What felt confusing or unhelpful?</label>
          <textarea id="beta-feedback-text" maxLength={4000} onChange={(event) => setText(event.target.value)} required value={text} />
          <small>Route and release are attached; Profile details are not.</small>
          <div><button disabled={status === "sending"} type="submit">{status === "sending" ? "Sending…" : "Send feedback"}</button><button onClick={() => setOpen(false)} type="button">Cancel</button></div>
          {status === "sent" ? <p role="status">Thanks—feedback sent.</p> : null}
          {status === "error" ? <p role="alert">Feedback could not be sent. Your text is still here.</p> : null}
        </form>
      ) : null}
    </aside>
  );
}
