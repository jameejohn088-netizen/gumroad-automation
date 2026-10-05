package com.gumroadautomation.util

/** Lightweight input validators shared by auth and settings forms. */
object Validators {

    // Pure-Kotlin regex (no android.util.Patterns) so this stays unit-testable on the JVM.
    private val EMAIL_REGEX = Regex("^[A-Za-z0-9+_.-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$")

    fun emailError(email: String): String? = when {
        email.isBlank() -> "Email is required"
        !EMAIL_REGEX.matches(email.trim()) -> "Enter a valid email address"
        else -> null
    }

    fun passwordError(password: String): String? = when {
        password.isEmpty() -> "Password is required"
        password.length < 8 -> "Password must be at least 8 characters"
        else -> null
    }

    fun baseUrlError(url: String): String? {
        val trimmed = url.trim().removeSuffix("/")
        return when {
            trimmed.isBlank() -> "Backend URL is required"
            !trimmed.startsWith("http://") && !trimmed.startsWith("https://") ->
                "URL must start with http:// or https://"
            trimmed.contains(" ") -> "URL must not contain spaces"
            else -> null
        }
    }

    fun normalizeBaseUrl(url: String): String {
        var u = url.trim().removeSuffix("/")
        if (!u.endsWith("/api/v1")) {
            // Accept a bare host like http://192.168.1.5:8000 and append the API prefix.
            u = "$u/api/v1"
        }
        return u
    }
}
