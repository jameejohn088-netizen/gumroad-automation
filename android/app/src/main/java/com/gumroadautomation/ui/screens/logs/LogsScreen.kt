package com.gumroadautomation.ui.screens.logs

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.ExperimentalMaterialApi
import androidx.compose.material.pullrefresh.PullRefreshIndicator
import androidx.compose.material.pullrefresh.pullRefresh
import androidx.compose.material.pullrefresh.rememberPullRefreshState
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gumroadautomation.data.api.dto.ActivityLogDto
import com.gumroadautomation.data.api.dto.ErrorLogDto
import com.gumroadautomation.data.api.dto.GumroadAccountDto
import com.gumroadautomation.data.api.dto.PageResponse
import com.gumroadautomation.data.datastore.SessionManager
import com.gumroadautomation.data.repository.AccountRepository
import com.gumroadautomation.data.repository.OpsRepository
import com.gumroadautomation.ui.components.AccountSelector
import com.gumroadautomation.ui.components.EmptyView
import com.gumroadautomation.ui.components.ErrorView
import com.gumroadautomation.ui.components.LoadingView
import com.gumroadautomation.ui.components.PagerFooter
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

@HiltViewModel
class LogsViewModel @Inject constructor(
    private val opsRepository: OpsRepository,
    private val accountRepository: AccountRepository,
    private val sessionManager: SessionManager,
) : ViewModel() {

    var tab by mutableIntStateOf(0) // 0 = activity, 1 = errors
    var activityPage by mutableIntStateOf(1)
    var errorPage by mutableIntStateOf(1)

    private val _activity =
        MutableStateFlow<ApiResult<PageResponse<ActivityLogDto>>>(ApiResult.Loading)
    val activity: StateFlow<ApiResult<PageResponse<ActivityLogDto>>> = _activity.asStateFlow()

    private val _errors =
        MutableStateFlow<ApiResult<PageResponse<ErrorLogDto>>>(ApiResult.Loading)
    val errors: StateFlow<ApiResult<PageResponse<ErrorLogDto>>> = _errors.asStateFlow()

    private val _accounts = MutableStateFlow<List<GumroadAccountDto>>(emptyList())
    val accounts: StateFlow<List<GumroadAccountDto>> = _accounts.asStateFlow()

    init {
        viewModelScope.launch {
            accountRepository.accounts().collect { result ->
                if (result is ApiResult.Success) _accounts.value = result.data
            }
        }
        refresh()
    }

    fun onAccountChanged() = refresh()
    fun refresh() {
        activityPage = 1
        errorPage = 1
        load()
    }

    fun loadMore() {
        if (tab == 0) {
            activityPage += 1
            loadActivity(append = true)
        } else {
            errorPage += 1
            loadErrors(append = true)
        }
    }

    private fun load() {
        loadActivity(append = false)
        loadErrors(append = false)
    }

    private fun loadActivity(append: Boolean) {
        viewModelScope.launch {
            val accountId = sessionManager.selectedAccountId.first()
            opsRepository.activityLogs(accountId, activityPage).collect { result ->
                _activity.value = if (append && result is ApiResult.Success &&
                    _activity.value is ApiResult.Success
                ) {
                    val prev = (_activity.value as ApiResult.Success).data
                    ApiResult.Success(
                        result.data.copy(items = prev.items + result.data.items)
                    )
                } else {
                    result
                }
            }
        }
    }

    private fun loadErrors(append: Boolean) {
        viewModelScope.launch {
            val accountId = sessionManager.selectedAccountId.first()
            opsRepository.errorLogs(accountId, errorPage).collect { result ->
                _errors.value = if (append && result is ApiResult.Success &&
                    _errors.value is ApiResult.Success
                ) {
                    val prev = (_errors.value as ApiResult.Success).data
                    ApiResult.Success(
                        result.data.copy(items = prev.items + result.data.items)
                    )
                } else {
                    result
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterialApi::class)
@Composable
fun LogsScreen(
    viewModel: LogsViewModel = hiltViewModel(),
    sessionViewModel: SessionViewModel,
) {
    val activity by viewModel.activity.collectAsState()
    val errors by viewModel.errors.collectAsState()
    val accounts by viewModel.accounts.collectAsState()
    val selectedId by sessionViewModel.selectedAccountId.collectAsState(initial = null)

    LaunchedEffect(selectedId) { viewModel.onAccountChanged() }

    val refreshing = activity is ApiResult.Loading || errors is ApiResult.Loading
    val pullState = rememberPullRefreshState(refreshing = refreshing, onRefresh = { viewModel.refresh() })

    androidx.compose.foundation.layout.Box(
        Modifier
            .fillMaxSize()
            .pullRefresh(pullState)
    ) {
        Column(Modifier.fillMaxSize()) {
            AccountSelector(
                accounts = accounts,
                selectedId = selectedId,
                onSelect = { sessionViewModel.selectAccount(it) },
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
            )
            TabRow(selectedTabIndex = viewModel.tab) {
                Tab(
                    selected = viewModel.tab == 0,
                    onClick = { viewModel.tab = 0 },
                    text = { Text("Activity") },
                )
                Tab(
                    selected = viewModel.tab == 1,
                    onClick = { viewModel.tab = 1 },
                    text = { Text("Errors") },
                )
            }
            if (viewModel.tab == 0) {
                when (val s = activity) {
                    is ApiResult.Loading -> LoadingView()
                    is ApiResult.Error -> ErrorView(s.message, onRetry = { viewModel.refresh() })
                    is ApiResult.Success -> LogList(
                        items = s.data.items.map {
                            Triple(it.action, it.details, it.createdAt)
                        },
                        page = viewModel.activityPage,
                        total = s.data.total,
                        onLoadMore = { viewModel.loadMore() },
                    )
                }
            } else {
                when (val s = errors) {
                    is ApiResult.Loading -> LoadingView()
                    is ApiResult.Error -> ErrorView(s.message, onRetry = { viewModel.refresh() })
                    is ApiResult.Success -> LogList(
                        items = s.data.items.map {
                            Triple(
                                it.message,
                                it.correlationId?.let { id -> "correlation: $id" },
                                it.createdAt,
                            )
                        },
                        page = viewModel.errorPage,
                        total = s.data.total,
                        errorStyle = true,
                        onLoadMore = { viewModel.loadMore() },
                    )
                }
            }
        }
        PullRefreshIndicator(refreshing, pullState, Modifier.align(Alignment.TopCenter))
    }
}

@Composable
private fun LogList(
    items: List<Triple<String, String?, String?>>,
    page: Int,
    total: Int,
    errorStyle: Boolean = false,
    onLoadMore: () -> Unit,
) {
    if (items.isEmpty()) {
        EmptyView("No log entries.")
        return
    }
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items(items) { (title, detail, createdAt) ->
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
            ) {
                Column(Modifier.padding(12.dp)) {
                    Text(
                        title,
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = if (errorStyle) MaterialTheme.colorScheme.error
                        else MaterialTheme.colorScheme.onSurface,
                    )
                    detail?.let {
                        Text(it, style = MaterialTheme.typography.bodySmall)
                    }
                    createdAt?.let {
                        Text(
                            DateUtils.formatDateTime(it),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }
        item {
            PagerFooter(
                page = page,
                hasMore = items.size < total,
                isLoading = false,
                onLoadMore = onLoadMore,
            )
        }
    }
}
