package com.gumroadautomation.ui.screens.more

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CardMembership
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Logout
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.SmartToy
import androidx.compose.material3.Divider
import androidx.compose.material3.Icon
import androidx.compose.material3.ListItem
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.hilt.navigation.compose.hiltViewModel
import com.gumroadautomation.ui.components.ConfirmDialog
import com.gumroadautomation.ui.screens.main.SessionViewModel
import com.gumroadautomation.ui.navigation.Routes
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue

@Composable
fun MoreScreen(
    onNavigate: (String) -> Unit,
    onLogout: () -> Unit,
    sessionViewModel: SessionViewModel,
) {
    var confirmLogout by remember { mutableStateOf(false) }

    val entries = listOf(
        Triple("Customers", Routes.CUSTOMERS, Icons.Filled.People),
        Triple("Subscribers", Routes.SUBSCRIBERS, Icons.Filled.Person),
        Triple("Memberships", Routes.MEMBERSHIPS, Icons.Filled.CardMembership),
        Triple("Automations", Routes.AUTOMATIONS, Icons.Filled.SmartToy),
        Triple("Scheduler", Routes.SCHEDULER, Icons.Filled.Schedule),
        Triple("Notifications", Routes.NOTIFICATIONS, Icons.Filled.Notifications),
        Triple("Logs", Routes.LOGS, Icons.Filled.History),
        Triple("Settings", Routes.SETTINGS, Icons.Filled.Settings),
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
    ) {
        entries.forEach { (label, route, icon) ->
            ListItem(
                headlineContent = { androidx.compose.material3.Text(label) },
                leadingContent = { Icon(icon, contentDescription = null) },
                modifier = Modifier.clickableNoRipple { onNavigate(route) },
            )
            Divider()
        }
        ListItem(
            headlineContent = {
                androidx.compose.material3.Text(
                    "Log out",
                    color = androidx.compose.material3.MaterialTheme.colorScheme.error,
                )
            },
            leadingContent = { Icon(Icons.Filled.Logout, contentDescription = null) },
            modifier = Modifier.clickableNoRipple { confirmLogout = true },
        )
    }

    if (confirmLogout) {
        ConfirmDialog(
            title = "Log out?",
            message = "Your session tokens will be wiped from this device and background sync will stop.",
            confirmLabel = "Log out",
            onConfirm = {
                confirmLogout = false
                sessionViewModel.logout()
                onLogout()
            },
            onDismiss = { confirmLogout = false },
        )
    }
}

/** Clickable modifier without ripple for list rows (kept in one place). */
@Composable
private fun Modifier.clickableNoRipple(onClick: () -> Unit): Modifier =
    this.clickable(
        indication = null,
        interactionSource = remember { androidx.compose.foundation.interaction.MutableInteractionSource() },
        onClick = onClick
    )
