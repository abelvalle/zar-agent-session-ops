import { DatePipe, DecimalPipe } from '@angular/common';
import { HttpClient, httpResource } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { MatTableModule } from '@angular/material/table';
import { MatToolbarModule } from '@angular/material/toolbar';
import { marked } from 'marked';
import { switchMap, takeWhile, timer } from 'rxjs';

interface TokenUsage {
  observed_at: string;
  input_tokens: number;
  cached_input_tokens: number;
  output_tokens: number;
  reasoning_output_tokens: number;
  total_tokens: number;
  model_context_window: number;
  rate_limit_used_percent: number | null;
  rate_limit_window_minutes: number | null;
  rate_limit_resets_at: string | null;
}

interface AgentSession {
  record_key: string;
  id: string;
  agent: string;
  title: string;
  status: string;
  repository: string;
  started_at: string;
  last_activity_at: string;
  size_bytes: number;
  event_count: number;
  origin: string;
  thread_source: string;
  last_event_type: string;
  usage: TokenUsage | null;
}

interface InventoryResponse {
  count: number;
  sessions: AgentSession[];
}

interface BlockedResponse extends InventoryResponse {
  threshold_hours: number;
}

interface RetentionResponse extends InventoryResponse {
  archive_after_days: number;
}

interface HealthResponse {
  status: string;
  version: string;
}

interface RefreshResponse {
  status: 'idle' | 'running' | 'completed' | 'failed';
  count: number | null;
  updated: number | null;
  reused: number | null;
  duration_seconds: number | null;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
}

interface GitHubReference {
  kind: 'issue' | 'pull' | 'commit';
  owner: string;
  repository: string;
  identifier: string;
  url: string;
  title?: string;
  state?: string;
  error?: string;
}

interface GitHubResponse {
  session_id: string;
  count: number;
  references: GitHubReference[];
}

interface ArchivePreview {
  record_key: string;
  session_id: string;
  title: string;
  source_name: string;
  destination_name: string;
  size_bytes: number;
  archive_after_days: number;
  confirmation: 'ARCHIVE';
}

interface ArchiveResult {
  record_key: string;
  session_id: string;
  title: string;
  destination_name: string;
  recovery_available: boolean;
}

interface ArchiveRecovery {
  record_key: string;
  session_id: string;
  title: string;
  agent: string;
  size_bytes: number;
  archived_at: string;
  destination_name: string;
}

interface ArchiveRecoveryResponse {
  count: number;
  archives: ArchiveRecovery[];
}

interface RestoreResult {
  record_key: string;
  session_id: string;
  restored: boolean;
  session: AgentSession;
}

type ArchiveStatus = 'idle' | 'loading' | 'preview' | 'archiving' | 'archived' | 'restoring';

type ReportName = 'weekly' | 'blocked' | 'sessions';

@Component({
  selector: 'app-root',
  imports: [
    DatePipe,
    DecimalPipe,
    MatButtonModule,
    MatFormFieldModule,
    MatPaginatorModule,
    MatProgressBarModule,
    MatSelectModule,
    MatTableModule,
    MatToolbarModule,
  ],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  private readonly http = inject(HttpClient);
  private readonly destroyRef = inject(DestroyRef);
  protected readonly displayedColumns = [
    'title',
    'agent',
    'status',
    'repository',
    'last_activity_at',
    'size_bytes',
    'tokens',
    'details',
  ];
  protected readonly agentFilter = signal('all');
  protected readonly statusFilter = signal('all');
  protected readonly pageIndex = signal(0);
  protected readonly pageSize = signal(25);
  protected readonly selectedSession = signal<AgentSession | null>(null);
  protected readonly locatedSession = signal<AgentSession | null>(null);
  protected readonly refreshState = signal<RefreshResponse | null>(null);
  protected readonly archiveStatus = signal<ArchiveStatus>('idle');
  protected readonly archivePreview = signal<ArchivePreview | null>(null);
  protected readonly archiveResult = signal<ArchiveResult | null>(null);
  protected readonly archiveError = signal<string | null>(null);
  protected readonly restoringKey = signal<string | null>(null);
  protected readonly recoveryError = signal<string | null>(null);
  protected readonly reportOptions: ReadonlyArray<{ id: ReportName; label: string }> = [
    { id: 'weekly', label: 'Semanal' },
    { id: 'blocked', label: 'Bloqueos' },
    { id: 'sessions', label: 'Inventario' },
  ];
  protected readonly selectedReport = signal<ReportName>('weekly');
  protected readonly health = httpResource<HealthResponse>(() => '/api/health');
  protected readonly inventory = httpResource<InventoryResponse>(() => '/api/sessions');
  protected readonly blocked = httpResource<BlockedResponse>(() => '/api/blocked');
  protected readonly retention = httpResource<RetentionResponse>(() => '/api/retention');
  protected readonly recoveries = httpResource<ArchiveRecoveryResponse>(() => '/api/archives');
  protected readonly report = httpResource.text(
    () => `/api/reports/${this.selectedReport()}`,
  );
  protected readonly github = httpResource<GitHubResponse>(() => {
    const session = this.selectedSession();
    return session ? `/api/sessions/${encodeURIComponent(session.id)}/github` : undefined;
  });

  protected readonly sessions = computed(() => this.inventory.value()?.sessions ?? []);
  protected readonly reportHtml = computed(() =>
    marked.parse(this.report.value() ?? '', { async: false, gfm: true }),
  );
  protected readonly usageSummary = computed(() => {
    const unique = new Map<string, AgentSession>();
    for (const session of this.sessions()) {
      if (!session.usage) {
        continue;
      }
      const stored = unique.get(session.id);
      if (!stored?.usage || stored.usage.total_tokens < session.usage.total_tokens) {
        unique.set(session.id, session);
      }
    }
    const items = [...unique.values()];
    const latest = items
      .filter((session) => session.usage?.rate_limit_used_percent !== null)
      .sort((left, right) =>
        (right.usage?.observed_at ?? '').localeCompare(left.usage?.observed_at ?? ''),
      )[0]?.usage;
    return {
      sessionCount: items.length,
      inputTokens: items.reduce((total, session) => total + (session.usage?.input_tokens ?? 0), 0),
      cachedInputTokens: items.reduce(
        (total, session) => total + (session.usage?.cached_input_tokens ?? 0),
        0,
      ),
      outputTokens: items.reduce(
        (total, session) => total + (session.usage?.output_tokens ?? 0),
        0,
      ),
      totalTokens: items.reduce((total, session) => total + (session.usage?.total_tokens ?? 0), 0),
      latest,
    };
  });
  protected readonly selectedReportLabel = computed(
    () =>
      this.reportOptions.find((option) => option.id === this.selectedReport())?.label ??
      'Informe',
  );
  protected readonly agents = computed(() =>
    [...new Set(this.sessions().map((session) => session.agent))].sort(),
  );
  protected readonly activeCount = computed(
    () => this.sessions().filter((session) => session.status === 'active').length,
  );
  protected readonly archivedCount = computed(
    () => this.sessions().filter((session) => session.status === 'archived').length,
  );
  protected readonly filteredSessions = computed(() =>
    this.sessions().filter(
      (session) =>
        (this.agentFilter() === 'all' || session.agent === this.agentFilter()) &&
        (this.statusFilter() === 'all' || session.status === this.statusFilter()),
    ),
  );
  protected readonly pagedSessions = computed(() => {
    const start = this.pageIndex() * this.pageSize();
    return this.filteredSessions().slice(start, start + this.pageSize());
  });
  protected readonly loading = computed(
    () =>
      this.refreshState()?.status === 'running' ||
      this.health.isLoading() ||
      this.inventory.isLoading() ||
      this.blocked.isLoading() ||
      this.retention.isLoading() ||
      this.recoveries.isLoading(),
  );
  protected readonly failed = computed(
    () =>
      !!(
        this.health.error() ||
        this.inventory.error() ||
        this.blocked.error() ||
        this.retention.error() ||
        this.recoveries.error()
      ),
  );

  protected refresh(): void {
    if (this.refreshState()?.status === 'running') {
      return;
    }
    this.refreshState.set({
      status: 'running',
      count: null,
      updated: null,
      reused: null,
      duration_seconds: null,
      started_at: null,
      finished_at: null,
      error: null,
    });
    this.http
      .post<RefreshResponse>('/api/refresh', {})
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (state) => {
          this.refreshState.set(state);
          if (state.status === 'running') {
            this.pollRefresh();
          } else if (state.status === 'completed') {
            this.reloadViews();
          }
        },
        error: () => this.refreshFailed(),
      });
  }

  private pollRefresh(): void {
    timer(0, 1000)
      .pipe(
        switchMap(() => this.http.get<RefreshResponse>('/api/refresh')),
        takeWhile((state) => state.status === 'running', true),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (state) => {
          this.refreshState.set(state);
          if (state.status === 'completed') {
            this.reloadViews();
          }
        },
        error: () => this.refreshFailed(),
      });
  }

  protected reloadViews(): void {
    this.health.reload();
    this.inventory.reload();
    this.blocked.reload();
    this.retention.reload();
    this.recoveries.reload();
    this.report.reload();
    if (this.selectedSession()) {
      this.github.reload();
    }
  }

  private refreshFailed(): void {
    this.refreshState.update((state) => ({
      status: 'failed',
      count: null,
      updated: null,
      reused: null,
      duration_seconds: null,
      started_at: state?.started_at ?? null,
      finished_at: null,
      error: 'No se pudo actualizar el inventario.',
    }));
  }

  protected setAgent(value: string): void {
    this.locatedSession.set(null);
    this.agentFilter.set(value);
    this.pageIndex.set(0);
  }

  protected setStatus(value: string): void {
    this.locatedSession.set(null);
    this.statusFilter.set(value);
    this.pageIndex.set(0);
  }

  protected setPage(event: PageEvent): void {
    this.locatedSession.set(null);
    this.pageIndex.set(event.pageIndex);
    this.pageSize.set(event.pageSize);
  }

  protected selectReport(report: ReportName): void {
    this.selectedReport.set(report);
  }

  protected locateSession(session: AgentSession): void {
    this.agentFilter.set(session.agent);
    this.statusFilter.set(session.status);
    const index = this.filteredSessions().findIndex(
      (item) =>
        item.id === session.id &&
        item.last_activity_at === session.last_activity_at &&
        item.size_bytes === session.size_bytes,
    );
    this.pageIndex.set(Math.max(0, Math.floor(index / this.pageSize())));
    this.locatedSession.set(session);
    setTimeout(() => {
      const row = document.getElementById(this.sessionDomId(session));
      if (typeof row?.scrollIntoView === 'function') {
        row.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      row?.focus({ preventScroll: true });
    });
  }

  protected openDetails(session: AgentSession): void {
    this.resetArchiveFlow();
    this.selectedSession.set(session);
  }

  protected closeDetails(): void {
    this.resetArchiveFlow();
    this.selectedSession.set(null);
  }

  protected reviewRetention(session: AgentSession): void {
    this.locateSession(session);
    this.openDetails(session);
    setTimeout(() => {
      const detail = document.querySelector('.session-detail');
      if (typeof detail?.scrollIntoView === 'function') {
        detail.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  }

  protected isRetentionCandidate(session: AgentSession): boolean {
    return (this.retention.value()?.sessions ?? []).some(
      (candidate) => candidate.record_key === session.record_key,
    );
  }

  protected prepareArchive(session: AgentSession): void {
    if (this.archiveStatus() !== 'idle') {
      return;
    }
    this.archiveError.set(null);
    this.archiveStatus.set('loading');
    this.http
      .get<ArchivePreview>(`/api/sessions/${session.record_key}/archive`)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (preview) => {
          this.archivePreview.set(preview);
          this.archiveStatus.set('preview');
        },
        error: () => {
          this.archiveError.set(
            'No se pudo preparar el archivado. Actualiza el inventario y vuelve a intentarlo.',
          );
          this.archiveStatus.set('idle');
        },
      });
  }

  protected cancelArchive(): void {
    this.archivePreview.set(null);
    this.archiveError.set(null);
    this.archiveStatus.set('idle');
  }

  protected confirmArchive(): void {
    const preview = this.archivePreview();
    if (!preview || this.archiveStatus() !== 'preview') {
      return;
    }
    this.archiveError.set(null);
    this.archiveStatus.set('archiving');
    this.http
      .post<ArchiveResult>(`/api/sessions/${preview.record_key}/archive`, {
        confirmation: preview.confirmation,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (result) => {
          this.archiveResult.set(result);
          this.archivePreview.set(null);
          this.archiveStatus.set('archived');
          this.reloadOperationalViews();
        },
        error: () => {
          this.archiveError.set(
            'No se archivó la sesión. Puede haber cambiado o existir ya un archivo con ese nombre.',
          );
          this.archiveStatus.set('preview');
        },
      });
  }

  protected restoreArchive(): void {
    const result = this.archiveResult();
    if (!result || this.archiveStatus() !== 'archived') {
      return;
    }
    this.archiveStatus.set('restoring');
    this.restoreRecord(result.record_key, true);
  }

  protected restoreRecovery(recovery: ArchiveRecovery): void {
    if (this.restoringKey()) {
      return;
    }
    this.restoreRecord(recovery.record_key, false);
  }

  private restoreRecord(recordKey: string, fromDetail: boolean): void {
    this.archiveError.set(null);
    this.recoveryError.set(null);
    this.restoringKey.set(recordKey);
    this.http
      .post<RestoreResult>(`/api/archives/${recordKey}/restore`, {})
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (restored) => {
          this.selectedSession.set(restored.session);
          this.archiveResult.set(null);
          this.archiveStatus.set('idle');
          this.restoringKey.set(null);
          this.reloadOperationalViews();
          if (!fromDetail) {
            setTimeout(() => {
              const detail = document.querySelector('.session-detail');
              if (typeof detail?.scrollIntoView === 'function') {
                detail.scrollIntoView({ behavior: 'smooth', block: 'start' });
              }
            });
          }
        },
        error: () => {
          const message = 'No se pudo restaurar. Comprueba que el destino original siga libre.';
          if (fromDetail) {
            this.archiveError.set(message);
          } else {
            this.recoveryError.set(message);
          }
          this.archiveStatus.set('archived');
          this.restoringKey.set(null);
        },
      });
  }

  private resetArchiveFlow(): void {
    this.archiveStatus.set('idle');
    this.archivePreview.set(null);
    this.archiveResult.set(null);
    this.archiveError.set(null);
    this.restoringKey.set(null);
  }

  private reloadOperationalViews(): void {
    this.inventory.reload();
    this.blocked.reload();
    this.retention.reload();
    this.recoveries.reload();
    this.report.reload();
  }

  protected isLocated(session: AgentSession): boolean {
    const located = this.locatedSession();
    return !!located && this.sessionRecordKey(located) === this.sessionRecordKey(session);
  }

  protected sessionDomId(session: AgentSession): string {
    return `session-${this.sessionRecordKey(session).replace(/[^a-zA-Z0-9_-]/g, '-')}`;
  }

  private sessionRecordKey(session: AgentSession): string {
    return session.record_key;
  }

  protected agentName(agent: string): string {
    return agent === 'chatgpt'
      ? 'ChatGPT'
      : agent === 'codex'
        ? 'Codex'
        : agent === 'claude'
          ? 'Claude Code'
          : agent;
  }

  protected statusName(status: string): string {
    return status === 'active'
      ? 'Activa'
      : status === 'archived'
        ? 'Archivada'
        : status === 'registered'
          ? 'Registrada'
          : status;
  }

  protected githubKindName(kind: GitHubReference['kind']): string {
    return kind === 'issue' ? 'Issue' : kind === 'pull' ? 'Pull request' : 'Commit';
  }

  protected githubStateName(state: string): string {
    return (
      { open: 'Abierta', closed: 'Cerrada', merged: 'Fusionada', available: 'Disponible' }[state] ??
      state
    );
  }

  protected formatBytes(bytes: number): string {
    if (bytes < 1024) {
      return `${bytes} B`;
    }
    if (bytes < 1024 ** 2) {
      return `${(bytes / 1024).toFixed(1)} KiB`;
    }
    return `${(bytes / 1024 ** 2).toFixed(1)} MiB`;
  }

  protected formatDuration(seconds: number | null): string {
    if (seconds === null) {
      return '—';
    }
    return seconds < 1 ? `${Math.round(seconds * 1000)} ms` : `${seconds.toFixed(1)} s`;
  }

  protected formatTokens(tokens: number, compact = false): string {
    const formatter = new Intl.NumberFormat('es-ES', {
      maximumFractionDigits: compact ? 1 : 0,
    });
    if (!compact) {
      return formatter.format(tokens);
    }
    if (tokens >= 1_000_000) {
      return `${formatter.format(tokens / 1_000_000)} M`;
    }
    if (tokens >= 1_000) {
      return `${formatter.format(tokens / 1_000)} mil`;
    }
    return formatter.format(tokens);
  }

  protected availablePercent(usage: TokenUsage): number {
    return Math.max(0, 100 - (usage.rate_limit_used_percent ?? 0));
  }

  protected uncachedInput(usage: TokenUsage): number {
    return Math.max(0, usage.input_tokens - usage.cached_input_tokens);
  }

  protected formatWindow(minutes: number | null): string {
    if (minutes === null) {
      return 'Ventana no indicada';
    }
    if (minutes % (24 * 60) === 0) {
      const days = minutes / (24 * 60);
      return `${days} ${days === 1 ? 'día' : 'días'}`;
    }
    return `${minutes} min`;
  }
}
