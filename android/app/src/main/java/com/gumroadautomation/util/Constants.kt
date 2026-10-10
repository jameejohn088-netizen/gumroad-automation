package com.gumroadautomation.util

/** App-wide constants. No secrets here — tokens live in encrypted storage only. */
object Constants {
    /** Default backend URL for the Android emulator (host machine's localhost). */
    const val DEFAULT_BASE_URL = "http://10.0.2.2:8000/api/v1"

    const val PREFS_DATASTORE_NAME = "settings"
    const val SECURE_PREFS_NAME = "secure_tokens"

    const val KEY_BASE_URL = "base_url"
    const val KEY_SELECTED_ACCOUNT_ID = "selected_account_id"
    const val KEY_THEME_MODE = "theme_mode" // system | light | dark
    const val KEY_SYNC_ENABLED = "sync_enabled"

    const val KEY_ACCESS_TOKEN = "access_token"
    const val KEY_REFRESH_TOKEN = "refresh_token"

    const val SYNC_WORK_NAME = "gumroad_periodic_sync"
    const val NOTIFICATION_CHANNEL_SYNC = "sync_channel"

    const val PAGE_SIZE = 20

    /** Gumroad connection states returned by the backend. */
    const val STATUS_CONNECTED = "connected"
    const val STATUS_NEEDS_RECONNECT = "needs_reconnect"
    const val STATUS_ERROR = "error"
    const val STATUS_DISABLED = "disabled"

    /**
     * Public gist raw URL holding the current backend base URL (one line, e.g.
     * "https://xxx.free.pinggy.net"). The watchdog keeps it fresh on rotation.
     * Empty until the /github-setup step is done — then auto-update is active.
     */
    const val GIST_RAW_URL = "https://gist.githubusercontent.com/jameejohn088/144c08133f0c412ce9d3f9d60191b4ff/raw/backend-url.txt"
}
