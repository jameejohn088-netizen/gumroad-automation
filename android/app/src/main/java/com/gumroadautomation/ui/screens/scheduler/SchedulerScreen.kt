package com.gumroadautomation.ui.screens.scheduler

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
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.pullrefresh.PullRefreshIndicator
import androidx.compose.material.pullrefresh.pullRefresh
import androidx.compose.material.pullrefresh.rememberPullRefreshState
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
import androidx.compose.material3.OutlinedButton
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
import com.gumroadautomation.data.api.dto.JobDto
import com.gumroadautomation.data.api.dto.JobExecutionDto
import com.gumroadautomation.data.api.dto.JobRequest
import com.gumroadautomation.data.datastore.SessionManager
import com.gumroadautomation.data.repository.AccountRepository
import com.gumroadautomation.data.repository.OpsRepository
import com.gumroadautomation.ui.components.AccountSelector
import com.gumroadautomation.ui.components.ConfirmDialog
import com.gumroadautomation.ui.components.EmptyView
import com.gumroadautomation.ui.components.ErrorView
import com.gumroadautomation.ui.components.LoadingView
import com.gumroadautomation.ui.components.StatusBadge
import com.gumroadautomation.ui.screens.main.SessionViewModel
import com.gumroadautomation.util.ApiResult
import com.gumroadautomation.util.DateUtils
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import javax.inject.Inject

val JOB_TYPES = listOf("sync", "automation", "export", "summary")
val SCHEDULE_OPTIONS = listOf("one_time", "recurring", "daily", "weekly")

@HiltViewModel
class SchedulerViewModel @Inject constructor(
    private val opsRepository: OpsRepository,
    private val accountRepository: AccountRepository,
    private val sessionManager: SessionManager,
) : ViewModel() {

    private val _state = MutableStateFlow<ApiResult<List<JobDto>>>(ApiResult.Loading)
    val state: StateFlow<ApiResult<List<JobDto>>> = _state.asStateFlow()

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
            opsRepository.jobs(accountId).collect { _state.value = it }
        }
    }

    fun onAccountChanged() = refresh()

    fun runNow(jobId: String) {
        viewModelScope.launch {
            opsRepository.runJobNow(jobId).collect { result ->
                when (result) {
                    is ApiResult.Loading -> Unit
                    is ApiResult.Success -> {
                        _message.value = result.data
                        refresh()
                    }
                    is ApiResult.Error -> _message.value = result.message
                }
            }
        }
    }

    fun delete(jobId: String) {
        viewModelScope.launch {
            opsRepository.deleteJob(jobId).collect { result ->
                when (result) {
                    is ApiResult.Loading -> Unit
                    is ApiResult.Success -> {
                        _message.value = "Job deleted"
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
fun SchedulerScreen(
    onOpenJob: (String) -> Unit,
    onEditJob: (String) -> Unit,
    onCreateJob: () -> Unit,
    viewModel: SchedulerViewModel = hiltViewModel(),
    sessionViewModel: SessionViewModel,
) {
    val state by viewModel.state.collectAsState()
    val accounts by viewModel.accounts.collectAsState()
    val message by viewModel.message.collectAsState()
    val selectedId by sessionViewModel.selectedAccountId.collectAsState(initial = null)
    val snackbar = remember { SnackbarHostState() }

    var deleteTarget by remember { mutableStateOf<JobDto?>(null) }

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
            FloatingActionButton(onClick = onCreateJob) {
                Icon(Icons.Filled.Add, contentDescription = "New job")
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
                                message = "No scheduled jobs yet. Create one for recurring syncs, automations, or exports.",
                                actionLabel = "New job",
                                onAction = onCreateJob,
                            )
                        } else {
                            LazyColumn(
                                modifier = Modifier.fillMaxSize(),
                                verticalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                items(s.data, key = { it.id }) { job ->
                                    JobCard(
                                        job = job,
                                        onOpen = { onOpenJob(job.id) },
                                        onRunNow = { viewModel.runNow(job.id) },
                                        onEdit = { onEditJob(job.id) },
                                        onDelete = { deleteTarget = job },
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

    deleteTarget?.let { job ->
        ConfirmDialog(
            title = "Delete job?",
            message = "“${job.name}” and its execution history will be deleted.",
            confirmLabel = "Delete",
            destructive = true,
            onConfirm = {
                viewModel.delete(job.id)
                deleteTarget = null
            },
            onDismiss = { deleteTarget = null },
        )
    }
}

@Composable
private fun JobCard(
    job: JobDto,
    onOpen: () -> Unit,
    onRunNow: () -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit,
) {
    Card(
        onClick = onOpen,
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp),
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(job.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text(
                        "${job.jobType} • ${job.schedule}" +
                            (job.nextRunAt?.let { " • next: ${DateUtils.formatDateTime(it)}" } ?: ""),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                StatusBadge(job.status)
                IconButton(onClick = onRunNow) {
                    Icon(Icons.Filled.PlayArrow, contentDescription = "Run now")
                }
            }
            Spacer(Modifier.height(4.dp))
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
// Job editor
// ---------------------------------------------------------------------------

@HiltViewModel
class JobEditorViewModel @Inject constructor(
    private val opsRepository: OpsRepository,
    private val sessionManager: SessionManager,
) : ViewModel() {

    var name by mutableStateOf("")
    var jobType by mutableStateOf(JOB_TYPES.first())
    var schedule by mutableStateOf(SCHEDULE_OPTIONS.first())
    var cron by mutableStateOf("")

    private val _saving = MutableStateFlow(false)
    val saving: StateFlow<Boolean> = _saving.asStateFlow()
    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()

    private var editingId: String? = null
    private var accountId: String? = null

    init {
        viewModelScope.launch {
            accountId = sessionManager.selectedAccountId.first()
        }
    }

    fun loadById(jobId: String) {
        editingId = jobId
        viewModelScope.launch {
            opsRepository.jobs(accountId).collect { result ->
                if (result is ApiResult.Success) {
                    result.data.firstOrNull { it.id == jobId }?.let { job ->
                        name = job.name
                        jobType = job.jobType
                        schedule = job.schedule
                        cron = job.cron.orEmpty()
                    }
                }
            }
        }
    }

    fun save(onSaved: () -> Unit) {
        if (name.isBlank()) {
            _error.value = "Job name is required"
            return
        }
        val request = JobRequest(
            accountId = accountId,
            name = name.trim(),
            jobType = jobType,
            schedule = schedule,
            cron = cron.trim().ifEmpty { null },
        )
        viewModelScope.launch {
            _saving.value = true
            _error.value = null
            opsRepository.saveJob(editingId, request).collect { result ->
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
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun JobDropdown(
    label: String,
    options: List<String>,
    selected: String,
    onSelect: (String) -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = !expanded }) {
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
fun JobEditorScreen(
    jobId: String?,
    onSaved: () -> Unit,
    onCancel: () -> Unit,
    viewModel: JobEditorViewModel = hiltViewModel(),
) {
    val saving by viewModel.saving.collectAsState()
    val error by viewModel.error.collectAsState()

    LaunchedEffect(jobId) {
        if (jobId != null) viewModel.loadById(jobId)
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        OutlinedTextField(
            value = viewModel.name,
            onValueChange = { viewModel.name = it },
            label = { Text("Job name") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        JobDropdown("Job type", JOB_TYPES, viewModel.jobType) { viewModel.jobType = it }
        JobDropdown("Schedule", SCHEDULE_OPTIONS, viewModel.schedule) { viewModel.schedule = it }
        OutlinedTextField(
            value = viewModel.cron,
            onValueChange = { viewModel.cron = it },
            label = { Text("Cron expression (for recurring)") },
            singleLine = true,
            placeholder = { Text("e.g. 0 9 * * *") },
            modifier = Modifier.fillMaxWidth(),
        )
        Text(
            "Jobs survive backend restarts and retry with exponential backoff. " +
                "Failed jobs land in a dead-letter state and can be re-run manually.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(8.dp))
        Button(
            onClick = { viewModel.save(onSaved) },
            enabled = !saving,
            modifier = Modifier.fillMaxWidth(),
        ) { Text(if (jobId == null) "Create job" else "Save changes") }
        TextButton(onClick = onCancel, modifier = Modifier.fillMaxWidth()) { Text("Cancel") }
    }
}

// ---------------------------------------------------------------------------
// Job detail + executions
// ---------------------------------------------------------------------------

@HiltViewModel
class JobDetailViewModel @Inject constructor(
    private val opsRepository: OpsRepository,
) : ViewModel() {

    private val _executions =
        MutableStateFlow<ApiResult<List<JobExecutionDto>>>(ApiResult.Loading)
    val executions: StateFlow<ApiResult<List<JobExecutionDto>>> = _executions.asStateFlow()

    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

    fun load(jobId: String) {
        viewModelScope.launch {
            opsRepository.executions(jobId).collect { _executions.value = it }
        }
    }

    fun retry(jobId: String, execId: String) {
        viewModelScope.launch {
            opsRepository.retryExecution(jobId, execId).collect { result ->
                when (result) {
                    is ApiResult.Loading -> Unit
                    is ApiResult.Success -> {
                        _message.value = result.data
                        load(jobId)
                    }
                    is ApiResult.Error -> _message.value = result.message
                }
            }
        }
    }

    fun runNow(jobId: String) {
        viewModelScope.launch {
            opsRepository.runJobNow(jobId).collect { result ->
                when (result) {
                    is ApiResult.Loading -> Unit
                    is ApiResult.Success -> {
                        _message.value = result.data
                        load(jobId)
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
fun JobDetailScreen(
    jobId: String,
    viewModel: JobDetailViewModel = hiltViewModel(),
) {
    val executions by viewModel.executions.collectAsState()
    val message by viewModel.message.collectAsState()
    val snackbar = remember { SnackbarHostState() }

    LaunchedEffect(jobId) { viewModel.load(jobId) }
    LaunchedEffect(message) {
        message?.let {
            snackbar.showSnackbar(it)
            viewModel.consumeMessage()
        }
    }

    val refreshing = executions is ApiResult.Loading
    val pullState = rememberPullRefreshState(refreshing = refreshing, onRefresh = { viewModel.load(jobId) })

    Scaffold(snackbarHost = { SnackbarHost(snackbar) }) { padding ->
        androidx.compose.foundation.layout.Box(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .pullRefresh(pullState)
        ) {
            Column(Modifier.fillMaxSize()) {
                message?.let { /* shown via snackbar */ }
                Row(
                    modifier = Modifier.padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        "Executions",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.weight(1f),
                    )
                    OutlinedButton(onClick = { viewModel.runNow(jobId) }) { Text("Run now") }
                }
                when (val s = executions) {
                    is ApiResult.Loading -> LoadingView()
                    is ApiResult.Error -> ErrorView(s.message, onRetry = { viewModel.load(jobId) })
                    is ApiResult.Success -> {
                        if (s.data.isEmpty()) {
                            EmptyView("No executions yet.")
                        } else {
                            LazyColumn(
                                modifier = Modifier.fillMaxSize(),
                                verticalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                items(s.data, key = { it.id }) { exec ->
                                    Card(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(horizontal = 16.dp),
                                    ) {
                                        Column(Modifier.padding(12.dp)) {
                                            Row(verticalAlignment = Alignment.CenterVertically) {
                                                Text(
                                                    DateUtils.formatDateTime(exec.startedAt),
                                                    style = MaterialTheme.typography.bodyMedium,
                                                    fontWeight = FontWeight.SemiBold,
                                                    modifier = Modifier.weight(1f),
                                                )
                                                StatusBadge(exec.status)
                                            }
                                            exec.finishedAt?.let {
                                                Text(
                                                    "Finished: ${DateUtils.formatDateTime(it)}",
                                                    style = MaterialTheme.typography.bodySmall,
                                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                                )
                                            }
                                            exec.result?.let {
                                                Text(it, style = MaterialTheme.typography.bodySmall)
                                            }
                                            exec.error?.let {
                                                Text(
                                                    it,
                                                    style = MaterialTheme.typography.bodySmall,
                                                    color = MaterialTheme.colorScheme.error,
                                                )
                                            }
                                            if (exec.status == "failed" || exec.status == "dead_letter") {
                                                Spacer(Modifier.height(4.dp))
                                                TextButton(onClick = { viewModel.retry(jobId, exec.id) }) {
                                                    Text("Retry execution")
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            PullRefreshIndicator(refreshing, pullState, Modifier.align(Alignment.TopCenter))
        }
    }
}
