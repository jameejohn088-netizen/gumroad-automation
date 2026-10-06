package com.gumroadautomation.ui.screens.automations

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.ExperimentalMaterialApi
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.pullrefresh.PullRefreshIndicator
import androidx.compose.material.pullrefresh.pullRefresh
import androidx.compose.material.pullrefresh.rememberPullRefreshState
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
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
import com.gumroadautomation.data.api.dto.AutomationRuleDto
import com.gumroadautomation.data.api.dto.AutomationRuleRequest
import com.gumroadautomation.data.api.dto.GumroadAccountDto
import com.gumroadautomation.data.api.dto.RuleActionDto
import com.gumroadautomation.data.api.dto.RuleConditionDto
import com.gumroadautomation.data.datastore.SessionManager
import com.gumroadautomation.data.repository.AccountRepository
import com.gumroadautomation.data.repository.AutomationRepository
import com.gumroadautomation.ui.components.AccountSelector
import com.gumroadautomation.ui.components.ConfirmDialog
import com.gumroadautomation.ui.components.EmptyView
import com.gumroadautomation.ui.components.ErrorView
import com.gumroadautomation.ui.components.LoadingView
import com.gumroadautomation.ui.screens.main.SessionViewModel
import com.gumroadautomation.util.ApiResult
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import javax.inject.Inject

// Only triggers the backend can really implement (polling diffs or webhooks).
val TRIGGER_OPTIONS = listOf(
    "new_sale", "refund", "new_subscriber", "subscription_cancelled",
    "subscription_ended", "product_change", "schedule", "sales_threshold",
)
val CONDITION_FIELDS = listOf(
    "product", "amount", "currency", "buyer_email_domain",
    "is_subscription", "account", "time_window", "first_time_buyer",
)
val CONDITION_OPERATORS = listOf(
    "equals", "not_equals", "greater_than", "less_than", "contains", "starts_with",
)
// Only actions backed by the real Gumroad API or local delivery.
val ACTION_TYPES = listOf(
    "notification", "offer_code_create", "offer_code_update", "offer_code_delete",
    "license_enable", "license_disable", "refund", "mark_shipped",
    "csv_export", "daily_summary", "webhook", "email",
)

@HiltViewModel
class AutomationsViewModel @Inject constructor(
    private val automationRepository: AutomationRepository,
    private val accountRepository: AccountRepository,
    private val sessionManager: SessionManager,
) : ViewModel() {

    private val _state =
        MutableStateFlow<ApiResult<List<AutomationRuleDto>>>(ApiResult.Loading)
    val state: StateFlow<ApiResult<List<AutomationRuleDto>>> = _state.asStateFlow()

    private val _accounts = MutableStateFlow<List<GumroadAccountDto>>(emptyList())
    val accounts: StateFlow<List<GumroadAccountDto>> = _accounts.asStateFlow()

    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

    init {
        viewModelScope.launch {
            accountRepository.accounts().collect { result ->
                if (result is ApiResult.Success) _accounts.value = result.data
            }
        }
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            val accountId = sessionManager.selectedAccountId.first()
            automationRepository.rules(accountId).collect { _state.value = it }
        }
    }

    fun onAccountChanged() = refresh()

    fun toggle(rule: AutomationRuleDto, enabled: Boolean) {
        viewModelScope.launch {
            automationRepository.toggleRule(rule, enabled).collect { result ->
                when (result) {
                    is ApiResult.Loading -> Unit
                    is ApiResult.Success -> refresh()
                    is ApiResult.Error -> _message.value = result.message
                }
            }
        }
    }

    fun delete(ruleId: String) {
        viewModelScope.launch {
            automationRepository.deleteRule(ruleId).collect { result ->
                when (result) {
                    is ApiResult.Loading -> Unit
                    is ApiResult.Success -> {
                        _message.value = "Rule deleted"
                        refresh()
                    }
                    is ApiResult.Error -> _message.value = result.message
                }
            }
        }
    }

    fun consumeMessage() {
        _message.value = null
    }
}

@OptIn(ExperimentalMaterialApi::class)
@Composable
fun AutomationsScreen(
    onEditRule: (String?) -> Unit,
    viewModel: AutomationsViewModel = hiltViewModel(),
    sessionViewModel: SessionViewModel,
) {
    val state by viewModel.state.collectAsState()
    val accounts by viewModel.accounts.collectAsState()
    val message by viewModel.message.collectAsState()
    val selectedId by sessionViewModel.selectedAccountId.collectAsState(initial = null)
    val snackbar = remember { SnackbarHostState() }

    var deleteTarget by remember { mutableStateOf<AutomationRuleDto?>(null) }

    LaunchedEffect(selectedId) { viewModel.onAccountChanged() }
    LaunchedEffect(message) {
        message?.let {
            snackbar.showSnackbar(it)
            viewModel.consumeMessage()
        }
    }

    val refreshing = state is ApiResult.Loading
    val pullState = rememberPullRefreshState(refreshing = refreshing, onRefresh = { viewModel.refresh() })

    Scaffold(
        snackbarHost = { SnackbarHost(snackbar) },
        floatingActionButton = {
            FloatingActionButton(onClick = { onEditRule(null) }) {
                Icon(Icons.Filled.Add, contentDescription = "New rule")
            }
        },
    ) { padding ->
        androidx.compose.foundation.layout.Box(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .pullRefresh(pullState)
        ) {
            Column(Modifier.fillMaxSize()) {
                AccountSelector(
                    accounts = accounts,
                    selectedId = selectedId,
                    onSelect = { sessionViewModel.selectAccount(it) },
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                )
                when (val s = state) {
                    is ApiResult.Loading -> LoadingView()
                    is ApiResult.Error -> ErrorView(s.message, onRetry = { viewModel.refresh() })
                    is ApiResult.Success -> {
                        if (s.data.isEmpty()) {
                            EmptyView(
                                message = "No automation rules yet. Create one to react to sales, refunds, and subscribers automatically.",
                                actionLabel = "New rule",
                                onAction = { onEditRule(null) },
                            )
                        } else {
                            LazyColumn(
                                modifier = Modifier.fillMaxSize(),
                                verticalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                items(s.data, key = { it.id }) { rule ->
                                    RuleCard(
                                        rule = rule,
                                        onToggle = { viewModel.toggle(rule, it) },
                                        onEdit = { onEditRule(rule.id) },
                                        onDelete = { deleteTarget = rule },
                                    )
                                }
                            }
                        }
                    }
                }
            }
            PullRefreshIndicator(refreshing, pullState, Modifier.align(Alignment.TopCenter))
        }
    }

    deleteTarget?.let { rule ->
        ConfirmDialog(
            title = "Delete rule?",
            message = "“${rule.name}” will be deleted. This cannot be undone.",
            confirmLabel = "Delete",
            destructive = true,
            onConfirm = {
                viewModel.delete(rule.id)
                deleteTarget = null
            },
            onDismiss = { deleteTarget = null },
        )
    }
}

@Composable
private fun RuleCard(
    rule: AutomationRuleDto,
    onToggle: (Boolean) -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp),
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(rule.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text(
                        "Trigger: ${rule.trigger} • ${rule.actions.size} action(s)" +
                            if (rule.dryRun) " • dry-run" else "",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Switch(checked = rule.enabled, onCheckedChange = onToggle)
            }
            Spacer(Modifier.height(8.dp))
            Row {
                TextButton(onClick = onEdit) { Text("Edit") }
                TextButton(onClick = onDelete) {
                    Text("Delete", color = MaterialTheme.colorScheme.error)
                }
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Rule builder
// ---------------------------------------------------------------------------

@HiltViewModel
class RuleEditorViewModel @Inject constructor(
    private val automationRepository: AutomationRepository,
    private val accountRepository: AccountRepository,
    private val sessionManager: SessionManager,
) : ViewModel() {

    var name by mutableStateOf("")
    var accountId by mutableStateOf<String?>(null)
    var trigger by mutableStateOf(TRIGGER_OPTIONS.first())
    var enabled by mutableStateOf(true)
    var dryRun by mutableStateOf(true)

    val conditions = mutableStateListOf<ConditionDraft>()
    val actions = mutableStateListOf<ActionDraft>()

    private val _accounts = MutableStateFlow<List<GumroadAccountDto>>(emptyList())
    val accounts: StateFlow<List<GumroadAccountDto>> = _accounts.asStateFlow()

    private val _saving = MutableStateFlow(false)
    val saving: StateFlow<Boolean> = _saving.asStateFlow()

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()

    private var editingId: String? = null

    init {
        viewModelScope.launch {
            accountRepository.accounts().collect { result ->
                if (result is ApiResult.Success) _accounts.value = result.data
            }
        }
        viewModelScope.launch {
            accountId = sessionManager.selectedAccountId.first()
        }
    }

    fun load(rule: AutomationRuleDto) {
        editingId = rule.id
        name = rule.name
        accountId = rule.accountId
        trigger = rule.trigger
        enabled = rule.enabled
        dryRun = rule.dryRun
        conditions.clear()
        conditions.addAll(rule.conditions.map {
            ConditionDraft(it.field, it.operator, it.value)
        })
        actions.clear()
        actions.addAll(rule.actions.map {
            ActionDraft(it.type, it.params.entries.joinToString(", ") { (k, v) -> "$k=$v" })
        })
    }

    fun loadById(ruleId: String) {
        viewModelScope.launch {
            val accountIdNow = sessionManager.selectedAccountId.first()
            automationRepository.rules(accountIdNow).collect { result ->
                if (result is ApiResult.Success) {
                    result.data.firstOrNull { it.id == ruleId }?.let { load(it) }
                }
            }
        }
    }

    fun save(onSaved: () -> Unit) {
        if (name.isBlank()) {
            _error.value = "Rule name is required"
            return
        }
        if (actions.isEmpty()) {
            _error.value = "Add at least one action"
            return
        }
        val request = AutomationRuleRequest(
            accountId = accountId,
            name = name.trim(),
            enabled = enabled,
            trigger = trigger,
            conditions = conditions.map {
                RuleConditionDto(it.field, it.operator, it.value.trim())
            },
            actions = actions.map {
                RuleActionDto(it.type, parseParams(it.paramsRaw))
            },
            dryRun = dryRun,
        )
        viewModelScope.launch {
            _saving.value = true
            _error.value = null
            automationRepository.saveRule(editingId, request).collect { result ->
                when (result) {
                    is ApiResult.Loading -> Unit
                    is ApiResult.Success -> {
                        _saving.value = false
                        onSaved()
                    }
                    is ApiResult.Error -> {
                        _saving.value = false
                        _error.value = result.message
                    }
                }
            }
        }
    }

    private fun parseParams(raw: String): Map<String, String> =
        raw.split(",")
            .map { it.trim() }
            .filter { it.contains("=") }
            .associate {
                val (k, v) = it.split("=", limit = 2)
                k.trim() to v.trim()
            }
}

data class ConditionDraft(var field: String, var operator: String, var value: String)
data class ActionDraft(var type: String, var paramsRaw: String)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DropdownField(
    label: String,
    options: List<String>,
    selected: String,
    onSelect: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    var expanded by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = { expanded = !expanded },
        modifier = modifier,
    ) {
        OutlinedTextField(
            value = selected,
            onValueChange = {},
            readOnly = true,
            label = { Text(label) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            modifier = Modifier
                .menuAnchor(MenuAnchorType.PrimaryNotEditable, true)
                .fillMaxWidth(),
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            options.forEach { option ->
                DropdownMenuItem(
                    text = { Text(option) },
                    onClick = { onSelect(option); expanded = false },
                )
            }
        }
    }
}

@Composable
fun RuleEditorScreen(
    ruleId: String?,
    onSaved: () -> Unit,
    onCancel: () -> Unit,
    viewModel: RuleEditorViewModel = hiltViewModel(),
    sessionViewModel: SessionViewModel,
) {
    val accounts by viewModel.accounts.collectAsState()
    val saving by viewModel.saving.collectAsState()
    val error by viewModel.error.collectAsState()
    val selectedId by sessionViewModel.selectedAccountId.collectAsState(initial = null)

    LaunchedEffect(ruleId) {
        if (ruleId != null) viewModel.loadById(ruleId)
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        error?.let {
            Text(it, color = MaterialTheme.colorScheme.error)
        }
        OutlinedTextField(
            value = viewModel.name,
            onValueChange = { viewModel.name = it },
            label = { Text("Rule name") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        AccountSelector(
            accounts = accounts,
            selectedId = viewModel.accountId ?: selectedId,
            onSelect = { viewModel.accountId = it },
        )
        DropdownField(
            label = "Trigger",
            options = TRIGGER_OPTIONS,
            selected = viewModel.trigger,
            onSelect = { viewModel.trigger = it },
        )
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Enabled", modifier = Modifier.weight(1f))
            Switch(checked = viewModel.enabled, onCheckedChange = { viewModel.enabled = it })
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Dry run (preview actions without executing)", modifier = Modifier.weight(1f))
            Switch(checked = viewModel.dryRun, onCheckedChange = { viewModel.dryRun = it })
        }

        Text("Conditions", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        viewModel.conditions.forEachIndexed { index, draft ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    DropdownField("Field", CONDITION_FIELDS, draft.field, {
                        viewModel.conditions[index] = draft.copy(field = it)
                    })
                    DropdownField("Operator", CONDITION_OPERATORS, draft.operator, {
                        viewModel.conditions[index] = draft.copy(operator = it)
                    })
                    OutlinedTextField(
                        value = draft.value,
                        onValueChange = {
                            viewModel.conditions[index] = draft.copy(value = it)
                        },
                        label = { Text("Value") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    TextButton(onClick = { viewModel.conditions.removeAt(index) }) {
                        Icon(Icons.Filled.Delete, contentDescription = null)
                        Spacer(Modifier.width(4.dp))
                        Text("Remove condition")
                    }
                }
            }
        }
        OutlinedButton(
            onClick = {
                viewModel.conditions.add(
                    ConditionDraft(CONDITION_FIELDS.first(), CONDITION_OPERATORS.first(), "")
                )
            },
            modifier = Modifier.fillMaxWidth(),
        ) { Text("Add condition") }

        Text("Actions", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        viewModel.actions.forEachIndexed { index, draft ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    DropdownField("Action type", ACTION_TYPES, draft.type, {
                        viewModel.actions[index] = draft.copy(type = it)
                    })
                    OutlinedTextField(
                        value = draft.paramsRaw,
                        onValueChange = {
                            viewModel.actions[index] = draft.copy(paramsRaw = it)
                        },
                        label = { Text("Parameters (key=value, comma-separated)") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    TextButton(onClick = { viewModel.actions.removeAt(index) }) {
                        Icon(Icons.Filled.Delete, contentDescription = null)
                        Spacer(Modifier.width(4.dp))
                        Text("Remove action")
                    }
                }
            }
        }
        OutlinedButton(
            onClick = { viewModel.actions.add(ActionDraft(ACTION_TYPES.first(), "")) },
            modifier = Modifier.fillMaxWidth(),
        ) { Text("Add action") }

        Spacer(Modifier.height(8.dp))
        Button(
            onClick = { viewModel.save(onSaved) },
            enabled = !saving,
            modifier = Modifier.fillMaxWidth(),
        ) { Text(if (ruleId == null) "Create rule" else "Save changes") }
        TextButton(onClick = onCancel, modifier = Modifier.fillMaxWidth()) { Text("Cancel") }
        Spacer(Modifier.height(16.dp))
    }
}
