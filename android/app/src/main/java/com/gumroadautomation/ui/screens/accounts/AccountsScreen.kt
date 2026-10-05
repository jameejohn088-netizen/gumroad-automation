package com.gumroadautomation.ui.screens.accounts

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.ExperimentalMaterialApi
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.pullrefresh.PullRefreshIndicator
import androidx.compose.material.pullrefresh.pullRefresh
import androidx.compose.material.pullrefresh.rememberPullRefreshState
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gumroadautomation.data.api.dto.GumroadAccountDto
import com.gumroadautomation.data.api.dto.SyncHistoryDto
import com.gumroadautomation.data.repository.AccountRepository
import com.gumroadautomation.ui.components.ConfirmDialog
import com.gumroadautomation.ui.components.EmptyView
import com.gumroadautomation.ui.components.ErrorView
import com.gumroadautomation.ui.components.LoadingView
import com.gumroadautomation.ui.components.PasswordField
import com.gumroadautomation.ui.components.StatusBadge
import com.gumroadautomation.ui.screens.main.SessionViewModel
import com.gumroadautomation.util.ApiResult
import com.gumroadautomation.util.DateUtils
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class AccountsViewModel @Inject constructor(
    private val accountRepository: AccountRepository,
) : ViewModel() {

    private val _state = MutableStateFlow<ApiResult<List<GumroadAccountDto>>>(ApiResult.Loading)
    val state: StateFlow<ApiResult<List<GumroadAccountDto>>> = _state.asStateFlow()

    private val _actionMessage = MutableStateFlow<String?>(null)
    val actionMessage: StateFlow<String?> = _actionMessage.asStateFlow()

    fun refresh() {
        viewModelScope.launch {
            accountRepository.accounts().collect { _state.value = it }
        }
    }

    private fun runAction(flow: kotlinx.coroutines.flow.Flow<ApiResult<*>>, successHint: String) {
        viewModelScope.launch {
            flow.collect { result ->
                when (result) {
                    is ApiResult.Loading -> Unit
                    is ApiResult.Success -> {
                        _actionMessage.value = successHint
                        refresh()
                    }
                    is ApiResult.Error -> _actionMessage.value = result.message
                }
            }
        }
    }

    fun createAccount(name: String) =
        runAction(accountRepository.createAccount(name), "Account added")

    fun connectManual(id: String, token: String) =
        runAction(accountRepository.connectManual(id, token), "Account connected")

    fun disconnect(id: String) =
        runAction(accountRepository.disconnect(id), "Account disconnected")

    fun reconnect(id: String) =
        runAction(accountRepository.reconnect(id), "Reconnect requested")

    fun enable(id: String) = runAction(accountRepository.enable(id), "Account enabled")
    fun disable(id: String) = runAction(accountRepository.disable(id), "Account disabled")

    fun syncNow(id: String) =
        runAction(accountRepository.syncNow(id), "Sync job queued")

    fun deleteAccount(id: String) =
        runAction(accountRepository.deleteAccount(id), "Account removed")

    fun consumeMessage() {
        _actionMessage.value = null
    }
}

@OptIn(ExperimentalMaterialApi::class)
@Composable
fun AccountsScreen(
    viewModel: AccountsViewModel = hiltViewModel(),
    sessionViewModel: SessionViewModel,
) {
    val state by viewModel.state.collectAsState()
    val message by viewModel.actionMessage.collectAsState()
    val snackbar = remember { SnackbarHostState() }

    var showAddDialog by remember { mutableStateOf(false) }
    var connectTarget by remember { mutableStateOf<GumroadAccountDto?>(null) }
    var deleteTarget by remember { mutableStateOf<GumroadAccountDto?>(null) }
    var historyTarget by remember { mutableStateOf<GumroadAccountDto?>(null) }

    LaunchedEffect(Unit) { viewModel.refresh() }
    LaunchedEffect(message) {
        message?.let {
            snackbar.showSnackbar(it)
            viewModel.consumeMessage()
            sessionViewModel.refreshAccounts()
        }
    }

    val refreshing = state is ApiResult.Loading
    val pullState = rememberPullRefreshState(refreshing = refreshing, onRefresh = { viewModel.refresh() })

    Scaffold(
        snackbarHost = { SnackbarHost(snackbar) },
        floatingActionButton = {
            FloatingActionButton(onClick = { showAddDialog = true }) {
                Icon(Icons.Filled.Add, contentDescription = "Add account")
            }
        },
    ) { padding ->
        androidx.compose.foundation.layout.Box(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .pullRefresh(pullState)
        ) {
            when (val s = state) {
                is ApiResult.Loading -> LoadingView()
                is ApiResult.Error -> ErrorView(s.message, onRetry = { viewModel.refresh() })
                is ApiResult.Success -> {
                    if (s.data.isEmpty()) {
                        EmptyView(
                            message = "No Gumroad accounts yet. Add your first account to start syncing.",
                            actionLabel = "Add account",
                            onAction = { showAddDialog = true },
                        )
                    } else {
                        LazyColumn(
                            modifier = Modifier.fillMaxSize(),
                            verticalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            items(s.data, key = { it.id }) { account ->
                                AccountCard(
                                    account = account,
                                    onConnect = { connectTarget = account },
                                    onDisconnect = { viewModel.disconnect(account.id) },
                                    onReconnect = { viewModel.reconnect(account.id) },
                                    onEnable = { viewModel.enable(account.id) },
                                    onDisable = { viewModel.disable(account.id) },
                                    onSync = { viewModel.syncNow(account.id) },
                                    onHistory = { historyTarget = account },
                                    onDelete = { deleteTarget = account },
                                )
                            }
                        }
                    }
                }
            }
            PullRefreshIndicator(refreshing, pullState, Modifier.align(Alignment.TopCenter))
        }
    }

    if (showAddDialog) {
        var name by remember { mutableStateOf("") }
        AlertDialog(
            onDismissRequest = { showAddDialog = false },
            title = { Text("Add Gumroad account") },
            text = {
                OutlinedTextField(
                    value = name, onValueChange = { name = it },
                    label = { Text("Account name") }, singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        viewModel.createAccount(name)
                        showAddDialog = false
                    },
                    enabled = name.isNotBlank(),
                ) { Text("Add") }
            },
            dismissButton = { TextButton(onClick = { showAddDialog = false }) { Text("Cancel") } },
        )
    }

    connectTarget?.let { account ->
        var token by remember { mutableStateOf("") }
        AlertDialog(
            onDismissRequest = { connectTarget = null },
            title = { Text("Connect ${account.name}") },
            text = {
                Column {
                    Text(
                        "Paste a Gumroad access token (generated on your Gumroad OAuth application page). " +
                            "It is sent to your backend over HTTPS and stored encrypted server-side — " +
                            "never on this device.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                    Spacer(Modifier.height(12.dp))
                    PasswordField(
                        value = token, onValueChange = { token = it },
                        label = "Gumroad access token",
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        viewModel.connectManual(account.id, token)
                        connectTarget = null
                    },
                    enabled = token.isNotBlank(),
                ) { Text("Connect") }
            },
            dismissButton = { TextButton(onClick = { connectTarget = null }) { Text("Cancel") } },
        )
    }

    deleteTarget?.let { account ->
        ConfirmDialog(
            title = "Remove account?",
            message = "“${account.name}” and all of its synced data (products, sales, customers, " +
                "automations, jobs, logs) will be deleted. This cannot be undone.",
            confirmLabel = "Remove",
            destructive = true,
            onConfirm = {
                viewModel.deleteAccount(account.id)
                deleteTarget = null
            },
            onDismiss = { deleteTarget = null },
        )
    }

    historyTarget?.let { account ->
        SyncHistoryDialog(accountId = account.id, onDismiss = { historyTarget = null })
    }
}

@Composable
private fun AccountCard(
    account: GumroadAccountDto,
    onConnect: () -> Unit,
    onDisconnect: () -> Unit,
    onReconnect: () -> Unit,
    onEnable: () -> Unit,
    onDisable: () -> Unit,
    onSync: () -> Unit,
    onHistory: () -> Unit,
    onDelete: () -> Unit,
) {
    var menuExpanded by remember { mutableStateOf(false) }
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp),
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(account.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text(
                        "Last sync: ${DateUtils.formatDateTime(account.lastSyncAt)}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                StatusBadge(account.status)
                androidx.compose.foundation.layout.Box {
                    TextButton(onClick = { menuExpanded = true }) { Text("⋮") }
                    DropdownMenu(
                        expanded = menuExpanded,
                        onDismissRequest = { menuExpanded = false },
                    ) {
                        DropdownMenuItem(
                            text = { Text("Connect / update token") },
                            onClick = { menuExpanded = false; onConnect() },
                        )
                        DropdownMenuItem(
                            text = { Text("Sync now") },
                            onClick = { menuExpanded = false; onSync() },
                        )
                        DropdownMenuItem(
                            text = { Text("Sync history") },
                            onClick = { menuExpanded = false; onHistory() },
                        )
                        DropdownMenuItem(
                            text = { Text("Reconnect") },
                            onClick = { menuExpanded = false; onReconnect() },
                        )
                        DropdownMenuItem(
                            text = { Text("Disconnect") },
                            onClick = { menuExpanded = false; onDisconnect() },
                        )
                        if (account.status == "disabled") {
                            DropdownMenuItem(
                                text = { Text("Enable") },
                                onClick = { menuExpanded = false; onEnable() },
                            )
                        } else {
                            DropdownMenuItem(
                                text = { Text("Disable") },
                                onClick = { menuExpanded = false; onDisable() },
                            )
                        }
                        DropdownMenuItem(
                            text = { Text("Remove", color = MaterialTheme.colorScheme.error) },
                            onClick = { menuExpanded = false; onDelete() },
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun SyncHistoryDialog(
    accountId: String,
    onDismiss: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Sync history") },
        text = { SyncHistoryBody(accountId = accountId) },
        confirmButton = { TextButton(onClick = onDismiss) { Text("Close") } },
    )
}

@Composable
private fun SyncHistoryBody(
    accountId: String,
    viewModel: SyncHistoryViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(accountId) { viewModel.load(accountId) }
    when (val s = state) {
        is ApiResult.Loading -> LoadingView()
        is ApiResult.Error -> Text(s.message, color = MaterialTheme.colorScheme.error)
        is ApiResult.Success -> {
            if (s.data.isEmpty()) {
                Text("No sync runs recorded yet.")
            } else {
                LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(s.data) { run ->
                        Column {
                            Text(
                                run.status,
                                style = MaterialTheme.typography.bodyMedium,
                                fontWeight = FontWeight.SemiBold,
                            )
                            Text(
                                "Started: ${DateUtils.formatDateTime(run.startedAt)}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            run.detail?.let {
                                Text(it, style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }
                }
            }
        }
    }
}

@HiltViewModel
class SyncHistoryViewModel @Inject constructor(
    private val accountRepository: AccountRepository,
) : ViewModel() {
    private val _state =
        MutableStateFlow<ApiResult<List<SyncHistoryDto>>>(ApiResult.Loading)
    val state: StateFlow<ApiResult<List<SyncHistoryDto>>> = _state.asStateFlow()

    fun load(accountId: String) {
        viewModelScope.launch {
            accountRepository.syncHistory(accountId).collect { _state.value = it }
        }
    }
}
