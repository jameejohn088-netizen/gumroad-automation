package com.gumroadautomation.ui.screens.sales

import androidx.compose.foundation.clickable
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
import androidx.compose.material.pullrefresh.PullRefreshIndicator
import androidx.compose.material.pullrefresh.pullRefresh
import androidx.compose.material.pullrefresh.rememberPullRefreshState
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
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
import com.gumroadautomation.data.api.dto.PageResponse
import com.gumroadautomation.data.api.dto.SaleDto
import com.gumroadautomation.data.datastore.SessionManager
import com.gumroadautomation.data.repository.AccountRepository
import com.gumroadautomation.data.repository.CatalogRepository
import com.gumroadautomation.ui.components.AccountSelector
import com.gumroadautomation.ui.components.ConfirmDialog
import com.gumroadautomation.ui.components.EmptyView
import com.gumroadautomation.ui.components.ErrorView
import com.gumroadautomation.ui.components.LoadingView
import com.gumroadautomation.ui.components.OfflineBanner
import com.gumroadautomation.ui.components.PagerFooter
import com.gumroadautomation.ui.components.SearchField
import com.gumroadautomation.ui.screens.main.SessionViewModel
import com.gumroadautomation.util.ApiResult
import com.gumroadautomation.util.DateUtils
import com.gumroadautomation.util.Money
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class SalesViewModel @Inject constructor(
    private val catalogRepository: CatalogRepository,
    private val accountRepository: AccountRepository,
    private val sessionManager: SessionManager,
) : ViewModel() {

    var query by mutableStateOf("")
    var page by mutableIntStateOf(1)

    private val _items = MutableStateFlow<List<SaleDto>>(emptyList())
    val items: StateFlow<List<SaleDto>> = _items.asStateFlow()
    private val _total = MutableStateFlow(0)
    val total: StateFlow<Int> = _total.asStateFlow()
    private val _loading = MutableStateFlow(false)
    val loading: StateFlow<Boolean> = _loading.asStateFlow()
    private val _refreshing = MutableStateFlow(false)
    val refreshing: StateFlow<Boolean> = _refreshing.asStateFlow()
    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()
    private val _offline = MutableStateFlow(false)
    val offline: StateFlow<Boolean> = _offline.asStateFlow()
    private val _accounts = MutableStateFlow<List<GumroadAccountDto>>(emptyList())
    val accounts: StateFlow<List<GumroadAccountDto>> = _accounts.asStateFlow()
    private val _actionResult = MutableStateFlow<String?>(null)
    val actionResult: StateFlow<String?> = _actionResult.asStateFlow()

    private var searchJob: Job? = null

    init {
        viewModelScope.launch {
            accountRepository.accounts().collect { result ->
                if (result is ApiResult.Success) _accounts.value = result.data
            }
        }
        load(reset = true)
    }

    fun onQueryChange(newQuery: String) {
        query = newQuery
        searchJob?.cancel()
        searchJob = viewModelScope.launch {
            delay(400)
            load(reset = true)
        }
    }

    fun onAccountChanged() = load(reset = true)
    fun refresh() {
        _refreshing.value = true
        load(reset = true)
    }

    fun loadMore() {
        if (_loading.value) return
        page += 1
        load(reset = false)
    }

    fun consumeActionResult() {
        _actionResult.value = null
    }

    fun refundSale(saleId: String, dryRun: Boolean) {
        viewModelScope.launch {
            catalogRepository.refundSale(saleId, dryRun).collect { result ->
                when (result) {
                    is ApiResult.Loading -> Unit
                    is ApiResult.Success ->
                        _actionResult.value = result.data.message.ifEmpty {
                            if (result.data.dryRun) "Dry run: refund would succeed."
                            else "Sale refunded."
                        }
                    is ApiResult.Error -> _actionResult.value = result.message
                }
            }
        }
    }

    fun markShipped(saleId: String, dryRun: Boolean) {
        viewModelScope.launch {
            catalogRepository.markShipped(saleId, dryRun).collect { result ->
                when (result) {
                    is ApiResult.Loading -> Unit
                    is ApiResult.Success ->
                        _actionResult.value = result.data.message.ifEmpty {
                            if (result.data.dryRun) "Dry run: mark-as-shipped would succeed."
                            else "Sale marked as shipped."
                        }
                    is ApiResult.Error -> _actionResult.value = result.message
                }
            }
        }
    }

    private fun load(reset: Boolean) {
        if (reset) {
            page = 1
            _items.value = emptyList()
        }
        viewModelScope.launch {
            _loading.value = true
            _error.value = null
            _offline.value = false
            val accountId = sessionManager.selectedAccountId.first()
            catalogRepository.sales(accountId, query, page).collect { result ->
                when (result) {
                    is ApiResult.Loading -> Unit
                    is ApiResult.Success -> {
                        _items.value = if (page == 1) result.data.items
                        else _items.value + result.data.items
                        _total.value = result.data.total
                        _loading.value = false
                        _refreshing.value = false
                    }
                    is ApiResult.Error -> {
                        _loading.value = false
                        _refreshing.value = false
                        @Suppress("UNCHECKED_CAST")
                        val cached = result.cached as? PageResponse<SaleDto>
                        if (cached != null && cached.items.isNotEmpty()) {
                            _items.value = cached.items
                            _total.value = cached.total
                            _offline.value = true
                        } else {
                            _error.value = result.message
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterialApi::class)
@Composable
fun SalesScreen(
    viewModel: SalesViewModel = hiltViewModel(),
    sessionViewModel: SessionViewModel,
) {
    val items by viewModel.items.collectAsState()
    val total by viewModel.total.collectAsState()
    val loading by viewModel.loading.collectAsState()
    val refreshing by viewModel.refreshing.collectAsState()
    val error by viewModel.error.collectAsState()
    val offline by viewModel.offline.collectAsState()
    val accounts by viewModel.accounts.collectAsState()
    val selectedId by sessionViewModel.selectedAccountId.collectAsState(initial = null)
    val actionResult by viewModel.actionResult.collectAsState()

    var detailSale by remember { mutableStateOf<SaleDto?>(null) }

    LaunchedEffect(selectedId) { viewModel.onAccountChanged() }

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
            SearchField(
                value = viewModel.query,
                onValueChange = { viewModel.onQueryChange(it) },
                placeholder = "Search by product or buyer email…",
                modifier = Modifier.padding(horizontal = 16.dp),
            )
            if (offline) OfflineBanner()
            actionResult?.let {
                Text(
                    it,
                    color = MaterialTheme.colorScheme.primary,
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
                )
                LaunchedEffect(it) {
                    kotlinx.coroutines.delay(4000)
                    viewModel.consumeActionResult()
                }
            }
            when {
                loading && items.isEmpty() -> LoadingView()
                error != null && items.isEmpty() -> ErrorView(error!!, onRetry = { viewModel.refresh() })
                items.isEmpty() -> EmptyView("No sales found.")
                else -> LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(items, key = { it.id }) { sale ->
                        SaleRow(sale = sale, onClick = { detailSale = sale })
                    }
                    item {
                        PagerFooter(
                            page = viewModel.page,
                            hasMore = items.size < total,
                            isLoading = loading,
                            onLoadMore = { viewModel.loadMore() },
                        )
                    }
                }
            }
        }
        PullRefreshIndicator(refreshing, pullState, Modifier.align(Alignment.TopCenter))
    }

    detailSale?.let { sale ->
        SaleDetailDialog(
            sale = sale,
            onDismiss = { detailSale = null },
            onRefund = { dryRun -> viewModel.refundSale(sale.id, dryRun) },
            onMarkShipped = { dryRun -> viewModel.markShipped(sale.id, dryRun) },
        )
    }
}

@Composable
private fun SaleRow(sale: SaleDto, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp)
            .clickable(onClick = onClick),
    ) {
        Column(Modifier.padding(12.dp)) {
            Row(Modifier.fillMaxWidth()) {
                Text(
                    sale.productName ?: "Sale",
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f),
                )
                Text(
                    Money.format(sale.amountCents, sale.currency),
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.Bold,
                )
            }
            val meta = buildList {
                sale.email?.let { add(it) }
                sale.createdAt?.let { add(DateUtils.formatDate(it)) }
                if (sale.refunded) add("Refunded")
                if (sale.shipped) add("Shipped")
                if (sale.isSubscription) add("Subscription")
            }.joinToString(" • ")
            if (meta.isNotEmpty()) {
                Text(
                    meta,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

/**
 * Sale detail with the two real Gumroad write actions. Both default to dry-run;
 * the destructive refund additionally requires an explicit confirmation dialog
 * before dry_run=false is ever sent.
 */
@Composable
private fun SaleDetailDialog(
    sale: SaleDto,
    onDismiss: () -> Unit,
    onRefund: (dryRun: Boolean) -> Unit,
    onMarkShipped: (dryRun: Boolean) -> Unit,
) {
    var dryRun by remember { mutableStateOf(true) }
    var confirmRefund by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(sale.productName ?: "Sale") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Buyer: ${sale.email ?: "—"}")
                Text("Amount: ${Money.format(sale.amountCents, sale.currency)}")
                Text("Date: ${DateUtils.formatDateTime(sale.createdAt)}")
                Text("Refunded: ${if (sale.refunded) "yes" else "no"} • Shipped: ${if (sale.shipped) "yes" else "no"}")
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("Dry run", modifier = Modifier.weight(1f))
                    Switch(checked = dryRun, onCheckedChange = { dryRun = it })
                }
                Text(
                    "Dry run previews the action on the backend without changing anything in Gumroad.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(4.dp))
                OutlinedButton(
                    onClick = {
                        if (dryRun) onRefund(true) else confirmRefund = true
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Refund sale") }
                OutlinedButton(
                    onClick = { onMarkShipped(dryRun) },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Mark as shipped") }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("Close") } },
    )

    if (confirmRefund) {
        ConfirmDialog(
            title = "Refund this sale?",
            message = "This will refund ${Money.format(sale.amountCents, sale.currency)} " +
                "to ${sale.email ?: "the buyer"} via Gumroad. This cannot be undone.",
            confirmLabel = "Refund now",
            destructive = true,
            onConfirm = {
                confirmRefund = false
                onRefund(false)
            },
            onDismiss = { confirmRefund = false },
        )
    }
}
