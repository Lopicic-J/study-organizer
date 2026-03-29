/**
 * stripe-webhook/index.ts
 * Supabase Edge Function — Stripe Webhook Handler (Deno-nativ, kein npm:stripe)
 *
 * Ablauf:
 *  1. Stripe feuert "checkout.session.completed"
 *  2. Signatur wird manuell via Web Crypto API geprueft (kein Stripe SDK -> kein Deno-Compat-Problem)
 *  3. SOAPP-Lizenzcode wird generiert (identisch zu license.py)
 *  4. Code wird in Supabase gespeichert
 *  5. Kunde erhaelt E-Mail via Resend
 */

// ─── Stripe Signatur-Verifikation (nativ, kein npm) ──────────────────────────

async function verifyStripeSignature(
  rawBody: string,
  sigHeader: string,
  secret: string,
): Promise<boolean> {
  // sigHeader Format: "t=1234567890,v1=abcdef...,v0=..."
  let timestamp = "";
  const v1Sigs: string[] = [];

  for (const part of sigHeader.split(",")) {
    const eq = part.indexOf("=");
    if (eq === -1) continue;
    const k = part.slice(0, eq);
    const v = part.slice(eq + 1);
    if (k === "t") timestamp = v;
    if (k === "v1") v1Sigs.push(v);
  }

  if (!timestamp || v1Sigs.length === 0) return false;

  // Toleranz: 5 Minuten
  const age = Math.abs(Date.now() / 1000 - parseInt(timestamp, 10));
  if (age > 300) {
    console.warn("Stripe timestamp too old:", age, "s");
    return false;
  }

  const signedPayload = `${timestamp}.${rawBody}`;
  const keyMat = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sigBytes = await crypto.subtle.sign(
    "HMAC",
    keyMat,
    new TextEncoder().encode(signedPayload),
  );
  const expected = Array.from(new Uint8Array(sigBytes))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");

  return v1Sigs.some((s) => s === expected);
}

// ─── SOAPP Lizenzcode-Generator (identisch zu license.py) ────────────────────

async function generateSOAPPCode(secret: string): Promise<string> {
  const HEX = "0123456789ABCDEF";
  const rand = new Uint8Array(6);
  crypto.getRandomValues(rand);
  let payload = "";
  for (const b of rand) payload += HEX[b % 16];

  const keyMat = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sigBytes = await crypto.subtle.sign(
    "HMAC",
    keyMat,
    new TextEncoder().encode(payload.toUpperCase()),
  );
  const hexFull = Array.from(new Uint8Array(sigBytes))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  const cs = hexFull.substring(0, 2).toUpperCase();

  return `SOAPP-${payload}-${cs}`;
}

// ─── Supabase Insert ──────────────────────────────────────────────────────────

async function insertLicenseCode(
  supabaseUrl: string,
  serviceKey: string,
  code: string,
  customerEmail: string,
  plan: string,
  stripeSessionId: string,
): Promise<void> {
  const res = await fetch(`${supabaseUrl}/rest/v1/license_codes`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "apikey": serviceKey,
      "Authorization": `Bearer ${serviceKey}`,
      "Prefer": "return=minimal",
    },
    body: JSON.stringify({
      code,
      used: false,
      created_at: new Date().toISOString(),
      customer_email: customerEmail,
      plan,
      stripe_session_id: stripeSessionId,
    }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Supabase insert failed (${res.status}): ${err}`);
  }
}

// ─── Resend E-Mail ────────────────────────────────────────────────────────────

async function sendLicenseEmail(
  resendKey: string,
  to: string,
  code: string,
  plan: string,
): Promise<void> {
  const planLabel: Record<string, string> = {
    monthly: "Pro Monatlich",
    halfyear: "Pro Halbjährlich",
    yearly: "Pro Jährlich",
  };

  const html = `
<!DOCTYPE html>
<html lang="de">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:system-ui,-apple-system,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f5;padding:40px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
        <tr>
          <td style="background:linear-gradient(135deg,#7C3AED,#6D28D9);padding:36px 40px;text-align:center;">
            <h1 style="margin:0;color:#ffffff;font-size:28px;font-weight:800;letter-spacing:-0.5px;">
              Semetra Pro
            </h1>
            <p style="margin:8px 0 0;color:rgba(255,255,255,0.85);font-size:15px;">
              ${planLabel[plan] ?? plan} - Aktivierungscode
            </p>
          </td>
        </tr>
        <tr>
          <td style="padding:36px 40px;">
            <p style="margin:0 0 20px;color:#374151;font-size:16px;line-height:1.6;">
              Danke fuer deinen Kauf!<br>
              Hier ist dein persoenlicher Lizenzcode fuer Semetra Pro:
            </p>
            <div style="background:#f3f0ff;border:2px solid #7C3AED;border-radius:10px;padding:24px;text-align:center;margin:24px 0;">
              <p style="margin:0 0 6px;font-size:12px;color:#7C3AED;font-weight:600;letter-spacing:1px;text-transform:uppercase;">
                Dein Lizenzcode
              </p>
              <p style="margin:0;font-size:22px;font-family:monospace;font-weight:700;color:#1f1235;letter-spacing:2px;">
                ${code}
              </p>
            </div>
            <p style="margin:24px 0 8px;color:#374151;font-size:15px;font-weight:600;">
              So aktivierst du Semetra Pro:
            </p>
            <ol style="margin:0;padding-left:20px;color:#4B5563;font-size:15px;line-height:2;">
              <li>Oeffne <strong>Semetra</strong> auf deinem Computer</li>
              <li>Gehe zu <strong>Einstellungen &rarr; Lizenz</strong></li>
              <li>Fuege den Code oben ein und klicke <strong>Aktivieren</strong></li>
            </ol>
            <div style="border-top:1px solid #e5e7eb;margin-top:32px;padding-top:20px;">
              <p style="margin:0;color:#9CA3AF;font-size:13px;line-height:1.6;">
                Bewahre diesen Code sicher auf - er ist personalisiert.<br>
                Bei Fragen: <a href="mailto:support@semetra.ch" style="color:#7C3AED;">support@semetra.ch</a>
              </p>
            </div>
          </td>
        </tr>
        <tr>
          <td style="background:#f9fafb;padding:20px 40px;text-align:center;">
            <p style="margin:0;color:#9CA3AF;font-size:12px;">
              &copy; 2025 Semetra &middot; <a href="https://semetra.ch" style="color:#7C3AED;text-decoration:none;">semetra.ch</a>
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>`;

  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${resendKey}`,
    },
    body: JSON.stringify({
      from: "Semetra <noreply@semetra.ch>",
      to: [to],
      subject: "Dein Semetra Pro Lizenzcode",
      html,
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Resend email failed: ${err}`);
  }
}

// ─── Plan-Erkennung ───────────────────────────────────────────────────────────

function detectPlan(session: Record<string, unknown>): string {
  const meta = (session["metadata"] ?? {}) as Record<string, string>;
  if (meta["plan"]) return meta["plan"];
  // Fallback: monatlich
  return "monthly";
}

// ─── Main Handler ─────────────────────────────────────────────────────────────

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  const webhookSecret = Deno.env.get("STRIPE_WEBHOOK_SECRET") ?? "";
  const supabaseUrl = Deno.env.get("SUPABASE_URL") ?? "";
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
  const resendKey = Deno.env.get("RESEND_API_KEY") ?? "";
  const soappSecret = Deno.env.get("SOAPP_HMAC_SECRET") ?? "";

  const signature = req.headers.get("stripe-signature") ?? "";
  const rawBody = await req.text();

  // Signatur pruefen
  const valid = await verifyStripeSignature(rawBody, signature, webhookSecret);
  if (!valid) {
    console.error("Invalid Stripe signature");
    return new Response("Invalid signature", { status: 400 });
  }

  let event: Record<string, unknown>;
  try {
    event = JSON.parse(rawBody) as Record<string, unknown>;
  } catch {
    return new Response("Invalid JSON", { status: 400 });
  }

  console.log("Event type:", event["type"]);

  try {
    if (event["type"] === "checkout.session.completed") {
      const session = event["data"] as Record<string, unknown>;
      const obj = session["object"] as Record<string, unknown>;

      const customerDetails = obj["customer_details"] as Record<string, unknown> | null;
      const email = (customerDetails?.["email"] as string) ?? (obj["customer_email"] as string) ?? "";

      if (!email) {
        console.warn("No customer email in session:", obj["id"]);
        return new Response(JSON.stringify({ received: true }), { status: 200 });
      }

      const plan = detectPlan(obj);
      const code = await generateSOAPPCode(soappSecret);

      console.log(`Generating code ${code} for ${email}, plan: ${plan}`);

      await insertLicenseCode(
        supabaseUrl,
        serviceKey,
        code,
        email,
        plan,
        obj["id"] as string,
      );

      console.log("DB insert OK");

      await sendLicenseEmail(resendKey, email, code, plan);

      console.log(`Email sent to ${email}`);
    }

    return new Response(JSON.stringify({ received: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    console.error("Webhook handler error:", err);
    return new Response(JSON.stringify({ received: true, error: String(err) }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }
});
