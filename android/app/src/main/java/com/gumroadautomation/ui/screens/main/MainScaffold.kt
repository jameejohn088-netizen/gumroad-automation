package com.gumroadautomation.ui.screens.main

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Dashboard
import androidx.compose.material.icons.filled.Inventory
import androidx.compose.material.icons.filled.MoreHoriz
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Receipt
import androidx.compose.material.icons.filled.SwapHoriz
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavController
import com.gumroadautomation.ui.navigation.Routes

private data class Tab(val route: String, val label: String, val icon: ImageVector)

private val TABS = listOf(
    Tab(Routes.DASHBOARD, "Dashboard", Icons.Filled.Dashboard),
    Tab(Routes.ACCOUNTS, "Accounts", Icons.Filled.SwapHoriz),
    Tab(Routes.PRODUCTS, "Products", Icons.Filled.Inventory),
    Tab(Routes.SALES, "Sales", Icons.Filled.Receipt),
    Tab(Routes.MORE, "More", Icons.Filled.MoreHoriz),
)

private fun titleFor(route: String): String = when (route) {
    Routes.DASHBOARD -> "Dashboard"
    Routes.ACCOUNTS -> "Gumroad Accounts"
    Routes.PRODUCTS -> "Products"
    Routes.SALES -> "Sales"
    Routes.MORE -> "More"
    Routes.CUSTOMERS -> "Customers"
    Routes.SUBSCRIBERS -> "Subscribers"
    Routes.MEMBERSHIPS -> "Memberships"
    Routes.AUTOMATIONS -> "Automations"
    Routes.RULE_EDITOR -> "Rule Editor"
    Routes.SCHEDULER -> "Scheduler"
    Routes.JOB_DETAIL -> "Job Details"
    Routes.JOB_EDITOR -> "Job Editor"
    Routes.NOTIFICATIONS -> "Notifications"
    Routes.LOGS -> "Logs"
    Routes.SETTINGS -> "Settings"
    else -> "Gumroad Automation"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScaffold(
    navController: NavController,
    currentRoute: String,
    sessionViewModel: SessionViewModel,
    content: @Composable () -> Unit,
) {
    val unread by sessionViewModel.unreadCount.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(titleFor(currentRoute)) },
                actions = {
                    IconButton(onClick = { navController.navigate(Routes.NOTIFICATIONS) }) {
                        BadgedBox(
                            badge = {
                                if (unread > 0) Badge { Text(unread.coerceAtMost(99).toString()) }
                            }
                        ) {
                            Icon(Icons.Filled.Notifications, contentDescription = "Notifications")
                        }
                    }
                }
            )
        },
        bottomBar = {
            NavigationBar {
                TABS.forEach { tab ->
                    NavigationBarItem(
                        selected = currentRoute == tab.route,
                        onClick = {
                            if (currentRoute != tab.route) {
                                navController.navigate(tab.route) {
                                    popUpTo(Routes.DASHBOARD) { saveState = true }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            }
                        },
                        icon = { Icon(tab.icon, contentDescription = tab.label) },
                        label = { Text(tab.label) },
                    )
                }
            }
        }
    ) { padding ->
        androidx.compose.foundation.layout.Box(Modifier.padding(padding)) {
            content()
        }
    }
}
