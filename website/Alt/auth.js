/* ═══════════════════════════════════════════════════════════════
   Semetra.ch — Auth Module (Supabase)
   Shared authentication logic for the static marketing site.
   Uses the same Supabase project as app.semetra.ch.
   ═══════════════════════════════════════════════════════════════ */

const SUPABASE_URL = "https://glnbdloeffeylfmzviis.supabase.co";
const SUPABASE_ANON_KEY = "sb_publishable_1Fzi1P7ZIqiBmS2qa-cZUw_hZgFHxt5";

let _supabase = null;

function getSupabase() {
  if (!_supabase) {
    _supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
  }
  return _supabase;
}

/* ─── Auth helpers ─── */

async function getUser() {
  const sb = getSupabase();
  const { data: { user } } = await sb.auth.getUser();
  return user;
}

async function getSession() {
  const sb = getSupabase();
  const { data: { session } } = await sb.auth.getSession();
  return session;
}

async function getProfile(userId) {
  const sb = getSupabase();
  const { data, error } = await sb
    .from("profiles")
    .select("*")
    .eq("id", userId)
    .single();
  if (error) return null;
  return data;
}

async function signIn(identifier, password) {
  const sb = getSupabase();
  let email = identifier;

  // If identifier doesn't look like an email, resolve username → email
  if (!identifier.includes("@")) {
    const { data, error } = await sb.rpc("get_email_by_username", {
      lookup_username: identifier,
    });
    if (error || !data) {
      throw { message: "Benutzername nicht gefunden." };
    }
    email = data;
  }

  const { data: authData, error: authError } = await sb.auth.signInWithPassword({ email, password });
  if (authError) throw authError;
  return authData;
}

async function signUp(email, password, country, extras) {
  const sb = getSupabase();
  const { data, error } = await sb.auth.signUp({
    email,
    password,
    options: {
      emailRedirectTo: window.location.origin + "/login.html?confirmed=1",
      data: { country },
    },
  });
  if (error) throw error;
  // Save country + optional fields to profile
  if (data?.user?.id) {
    const profileData = { country };
    if (extras?.username) profileData.username = extras.username;
    if (extras?.university) profileData.university = extras.university;
    if (extras?.study_program) profileData.study_program = extras.study_program;
    await sb.from("profiles").update(profileData).eq("id", data.user.id);
  }
  return data;
}

async function signOut() {
  const sb = getSupabase();
  await sb.auth.signOut();
  window.location.href = "/";
}

async function resetPassword(email) {
  const sb = getSupabase();
  const { error } = await sb.auth.resetPasswordForEmail(email, {
    redirectTo: window.location.origin + "/login.html",
  });
  if (error) throw error;
}

async function updateProfile(userId, updates) {
  const sb = getSupabase();
  const { data, error } = await sb
    .from("profiles")
    .update(updates)
    .eq("id", userId)
    .select()
    .single();
  if (error) throw error;
  return data;
}

async function getAiUsage(userId) {
  const sb = getSupabase();
  const now = new Date();
  const month = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const { data } = await sb
    .from("ai_usage")
    .select("used, addon_credits")
    .eq("user_id", userId)
    .eq("month", month)
    .single();
  return data || { used: 0, addon_credits: 0 };
}

/* ─── Username helpers ─── */

function isValidUsername(username) {
  return /^[a-z0-9_-]{3,30}$/.test(username);
}

async function isUsernameAvailable(username) {
  const sb = getSupabase();
  const { data, error } = await sb.rpc("get_email_by_username", {
    lookup_username: username,
  });
  // If the function doesn't exist yet (migration not run), treat as available
  if (error) {
    console.warn("Username check failed:", error.message);
    return true;
  }
  return !data; // null = available
}

/* ─── Navigation Auth State ─── */

async function updateNavAuth() {
  const user = await getUser();
  const authDesktop = document.getElementById("nav-auth-desktop");
  const authMobile = document.getElementById("nav-auth-mobile");
  const ctaBtn = document.querySelector(".nav-cta");

  // Preserve lang-switch toggle when updating auth section
  const langSwitchHTML = '<div class="lang-switch" onclick="toggleLang()"><span class="lang-opt" data-lang="de">DE</span><span class="lang-opt" data-lang="en">EN</span></div>';

  if (user) {
    const profile = await getProfile(user.id);
    const name = profile?.username || profile?.full_name || user.email?.split("@")[0] || "Profil";
    const isPro = profile?.plan === "pro";
    const badge = isPro
      ? '<span class="nav-pro-badge">PRO</span>'
      : "";

    if (authDesktop) {
      authDesktop.innerHTML = langSwitchHTML + `
        <a href="profil.html" class="nav-user-link">
          <span class="nav-user-avatar">${name.charAt(0).toUpperCase()}</span>
          <span class="nav-user-name">${name}</span>
          ${badge}
        </a>
      `;
    }
    if (ctaBtn) {
      ctaBtn.href = "profil.html";
      ctaBtn.textContent = "Mein Konto";
    }
    if (authMobile) {
      authMobile.innerHTML = `
        <a href="profil.html" class="nav-mobile-cta">Mein Profil</a>
        <a href="#" onclick="signOut(); return false;" style="text-align:center; color:var(--ink-40); font-size:0.9rem;">Abmelden</a>
      `;
    }
  } else {
    if (authDesktop) {
      authDesktop.innerHTML = langSwitchHTML + `
        <a href="login.html" class="nav-login-link" data-de="Anmelden" data-en="Sign in">Anmelden</a>
        <a href="register.html" class="nav-cta" data-de="Registrieren" data-en="Sign up">Registrieren</a>
      `;
    }
    if (authMobile) {
      authMobile.innerHTML = `
        <a href="login.html" data-de="Anmelden" data-en="Sign in">Anmelden</a>
        <a href="register.html" class="nav-mobile-cta" data-de="Registrieren" data-en="Sign up">Registrieren</a>
      `;
    }
  }

  // Re-apply language after auth update replaced DOM elements
  if (typeof applyLang === "function") {
    const lang = localStorage.getItem("semetra_lang") || "de";
    applyLang(lang);
  }
}

/* ─── Plan Display Helpers ─── */

function getPlanLabel(profile) {
  if (!profile) return { label: "Free", color: "#6b7280", bg: "#f3f4f6" };
  if (profile.plan_type === "lifetime" && profile.plan === "pro") {
    return {
      label: profile.plan_tier === "full" ? "Lifetime Full" : "Lifetime Basic",
      color: "#7c3aed",
      bg: "#ede9fe",
    };
  }
  if (profile.plan === "pro") {
    return {
      label: profile.plan_tier === "full" ? "Pro Full" : "Pro Basic",
      color: "#4f46e5",
      bg: "#eef2ff",
    };
  }
  return { label: "Free", color: "#6b7280", bg: "#f3f4f6" };
}

function getSubscriptionStatus(profile) {
  if (!profile || profile.plan === "free") return "Kein Abo";
  if (profile.plan_type === "lifetime") return "Lifetime — unbegrenzt";
  const status = profile.stripe_subscription_status;
  if (status === "active") return "Aktiv";
  if (status === "trialing") return "Testphase";
  if (status === "canceled" || status === "past_due") {
    if (profile.plan_expires_at) {
      const exp = new Date(profile.plan_expires_at);
      const days = Math.ceil((exp - new Date()) / 86400000);
      if (days > 0) return `Läuft aus in ${days} Tagen`;
      return "Abgelaufen";
    }
    return "Gekündigt";
  }
  return status || "Unbekannt";
}

function getAiPool(profile) {
  if (!profile || profile.plan === "free") return 3;
  if (profile.plan_type === "lifetime") {
    return profile.plan_tier === "full" ? 20 : 0;
  }
  return profile.plan_tier === "full" ? 100 : 10;
}

/* ─── Init ─── */
document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("nav-auth-desktop") || document.querySelector(".nav-cta")) {
    updateNavAuth();
  }
});
