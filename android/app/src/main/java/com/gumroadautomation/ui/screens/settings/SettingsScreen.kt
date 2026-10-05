package com.gumroadautomation.ui.screens.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.Divider
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
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
import com.gumroadautomation.BuildConfig
import com.gumroadautomation.data.api.ApiProvider
import com.gumroadautomation.data.api.dto.UserDto
import com.gumroadautomation.data.datastore.SessionManager
import com.gumroadautomation.data.repository.AuthRepository
import com.gumroadautomation.ui.components.ConfirmDialog
import com.gumroadautomation.ui.components.LoadingView
import com.gumroadautomation.ui.components.PasswordField
import com.gumroadautomation.ui.components.SectionTitle
import com.gumroadautomation.ui.screens.main.SessionViewModel
import com.gumroadautomation.util.ApiResult
import com.gumroadautomation.util.Constants
import com.gumroadautomation.util.Validators
import com.gumroadautomation.worker.SyncScheduler
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val authRepository: AuthRepository,
    private val sessionManager: SessionManager,
    private val apiProvider: ApiProvider,
    private val syncScheduler: SyncScheduler,
) : ViewModel() {

    private val _profile = MutableStateFlow<ApiResult<UserDto>>(ApiResult.Loading)
    val profile: StateFlow<ApiResult<UserDto>> = _profile.asStateFlow()

    val themeMode = sessionManager.themeMode
    val syncEnabled = sessionManager.syncEnabled

    private val _baseUrl = MutableStateFlow(Constants.DEFAULT_BASE_URL)
    val baseUrl: StateFlow<String> = _baseUrl.asStateFlow()

    private val _message = MutableStateFlow<String?>(null)
    val message: StateFlow<String?> = _message.asStateFlow()

    init {
        viewModelScope.launch {
            _baseUrl.value = sessionManager.baseUrl.first()
        }
        refreshProfile()
    }

    fun refreshProfile() {
        viewModelScope.launch {
            authRepository.me().collect { _profile.value = it }
        }
    }

    fun saveBaseUrl(raw: String) {
        val error = Validators.baseUrlError(raw)
        if (error != null) {
            _message.value = error
            return
        }
        viewModelScope.launch {
            val normalized = Validators.normalizeBaseUrl(raw)
            sessionManager.setBaseUrl(normalized)
            apiProvider.invalidate()
            _baseUrl.value = normalized
            _message.value = "Backend URL saved. Pull to refresh to reconnect."
        }
    }

    fun setThemeMode(mode: String) {
        viewModelScope.launch { sessionManager.setThemeMode(mode) }
    }

    fun setSyncEnabled(enabled: Boolean) {
        viewModelScope.launch {
            sessionManager.setSyncEnabled(enabled)
            if (enabled) syncScheduler.schedule() else syncScheduler.cancel()
            _message.value = if (enabled) "Background sync enabled"
            else "Background sync disabled"
        }
    }

    fun updateName(name: String) {
        viewModelScope.launch {
            authRepository.updateProfile(name).collect { result ->
                when (result) {
                    is ApiResult.Loading -> Unit
                    is ApiResult.Success -> {
                        _profile.value = result
                        _message.value = "Profile updated"
                    }
                    is ApiResult.Error -> _message.value = result.message
                }
            }
        }
    }

    fun changePassword(current: String, new: String) {
        viewModelScope.launch {
            authRepository.changePassword(current, new).collect { result ->
                when (result) {
                    is ApiResult.Loading -> Unit
                    is ApiResult.Success -> _message.value = "Password changed"
                    is ApiResult.Error -> _message.value = result.message
                }
            }
        }
    }

    fun consumeMessage() {
        _message.value = null
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    viewModel: SettingsViewModel = hiltViewModel(),
    sessionViewModel: SessionViewModel,
) {
    val profile by viewModel.profile.collectAsState()
    val themeMode by viewModel.themeMode.collectAsState(initial = "system")
    val syncEnabled by viewModel.syncEnabled.collectAsState(initial = true)
    val baseUrl by viewModel.baseUrl.collectAsState()
    val message by viewModel.message.collectAsState()

    var urlDraft by remember(baseUrl) { mutableStateOf(baseUrl) }
    var showChangePassword by remember { mutableStateOf(false) }
    var confirmLogout by remember { mutableStateOf(false) }

    LaunchedEffect(message) {
        if (message != null) {
            kotlinx.coroutines.delay(3500)
            viewModel.consumeMessage()
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(bottom = 24.dp),
    ) {
        message?.let {
            Text(
                it,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
            )
        }

        SectionTitle("Profile")
        when (val p = profile) {
            is ApiResult.Loading -> LoadingView()
            is ApiResult.Error -> Text(
                p.message,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(horizontal = 16.dp),
            )
            is ApiResult.Success -> ProfileCard(
                user = p.data,
                onSaveName = { viewModel.updateName(it) },
                onChangePassword = { showChangePassword = true },
            )
        }

        SectionTitle("Backend connection")
        Card(Modifier.padding(horizontal = 16.dp)) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    "Emulator: ${Constants.DEFAULT_BASE_URL}\n" +
                        "Real device: use your PC's LAN IP, e.g. http://192.168.1.10:8000 " +
                        "(same Wi-Fi, backend running, firewall open) or ADB reverse.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                OutlinedTextField(
                    value = urlDraft,
                    onValueChange = { urlDraft = it },
                    label = { Text("Backend base URL") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Button(
                    onClick = { viewModel.saveBaseUrl(urlDraft) },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Save backend URL") }
            }
        }

        SectionTitle("Appearance")
        Card(Modifier.padding(horizontal = 16.dp)) {
            var expanded by remember { mutableStateOf(false) }
            ExposedDropdownMenuBox(
                expanded = expanded,
                onExpandedChange = { expanded = !expanded },
                modifier = Modifier.padding(16.dp),
            ) {
                OutlinedTextField(
                    value = themeMode.replaceFirstChar { it.uppercase() },
                    onValueChange = {},
                    readOnly = true,
                    label = { Text("Theme") },
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
                    modifier = Modifier
                        .menuAnchor(MenuAnchorType.PrimaryNotEditable, true)
                        .fillMaxWidth(),
                )
                ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                    listOf("system", "light", "dark").forEach { mode ->
                        DropdownMenuItem(
                            text = { Text(mode.replaceFirstChar { it.uppercase() }) },
                            onClick = {
                                viewModel.setThemeMode(mode)
                                expanded = false
                            },
                        )
                    }
                }
            }
        }

        SectionTitle("Background sync")
        Card(Modifier.padding(horizontal = 16.dp)) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("Periodic background sync", modifier = Modifier.weight(1f))
                    Switch(checked = syncEnabled, onCheckedChange = { viewModel.setSyncEnabled(it) })
                }
                // Honest disclosure, required by the project spec.
                Text(
                    "Background sync runs at most every 15 minutes (a WorkManager limit). " +
                        "Android may delay, batch, or stop background work to save battery — " +
                        "it is best-effort, not guaranteed. True 24/7 automation while your " +
                        "phone is offline needs a continuously running server.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                OutlinedButton(
                    onClick = {
                        // Immediate user-triggered sync (still subject to OS scheduling).
                        viewModel.setSyncEnabled(true)
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Sync now") }
            }
        }

        SectionTitle("Session")
        Card(Modifier.padding(horizontal = 16.dp)) {
            Column(Modifier.padding(16.dp)) {
                Text("App version: ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})")
                Spacer(Modifier.height(8.dp))
                Button(
                    onClick = { confirmLogout = true },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Log out") }
            }
        }
    }

    if (showChangePassword) {
        var current by remember { mutableStateOf("") }
        var newPass by remember { mutableStateOf("") }
        var confirm by remember { mutableStateOf("") }
        var localError by remember { mutableStateOf<String?>(null) }
        androidx.compose.material3.AlertDialog(
            onDismissRequest = { showChangePassword = false },
            title = { Text("Change password") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    localError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                    PasswordField(value = current, onValueChange = { current = it }, label = "Current password")
                    PasswordField(value = newPass, onValueChange = { newPass = it }, label = "New password")
                    PasswordField(value = confirm, onValueChange = { confirm = it }, label = "Confirm new password")
                }
            },
            confirmButton = {
                Button(onClick = {
                    val err = Validators.passwordError(newPass)
                        ?: if (newPass != confirm) "Passwords do not match" else null
                    if (err != null) {
                        localError = err
                    } else {
                        viewModel.changePassword(current, newPass)
                        showChangePassword = false
                    }
                }) { Text("Change") }
            },
            dismissButton = { TextButton(onClick = { showChangePassword = false }) { Text("Cancel") } },
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
            },
            onDismiss = { confirmLogout = false },
        )
    }
}

@Composable
private fun ProfileCard(
    user: UserDto,
    onSaveName: (String) -> Unit,
    onChangePassword: () -> Unit,
) {
    var nameDraft by remember(user.id) { mutableStateOf(user.name.orEmpty()) }
    var editing by remember { mutableStateOf(false) }
    Card(Modifier.padding(horizontal = 16.dp)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(user.email, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.SemiBold)
            Text(
                if (user.emailVerified) "Email verified" else "Email not verified",
                style = MaterialTheme.typography.bodySmall,
                color = if (user.emailVerified) MaterialTheme.colorScheme.primary
                else MaterialTheme.colorScheme.error,
            )
            Divider()
            if (editing) {
                OutlinedTextField(
                    value = nameDraft,
                    onValueChange = { nameDraft = it },
                    label = { Text("Name") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Row {
                    Button(onClick = {
                        onSaveName(nameDraft)
                        editing = false
                    }) { Text("Save") }
                    Spacer(Modifier.padding(4.dp))
                    TextButton(onClick = { editing = false }) { Text("Cancel") }
                }
            } else {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("Name: ${user.name ?: "—"}", modifier = Modifier.weight(1f))
                    TextButton(onClick = { editing = true }) { Text("Edit") }
                }
            }
            OutlinedButton(onClick = onChangePassword, modifier = Modifier.fillMaxWidth()) {
                Text("Change password")
            }
        }
    }
}
