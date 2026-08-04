import { DatePipe } from '@angular/common';
import { httpResource } from '@angular/common/http';
import { Component, computed, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { MatTableModule } from '@angular/material/table';
import { MatToolbarModule } from '@angular/material/toolbar';

interface AgentSession {
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
}

interface InventoryResponse {
  count: number;
  sessions: AgentSession[];
}

interface BlockedResponse extends InventoryResponse {
  threshold_hours: number;
}

interface HealthResponse {
  status: string;
  version: string;
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

@Component({
  selector: 'app-root',
  imports: [
    DatePipe,
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
  protected readonly displayedColumns = [
    'title',
    'agent',
    'status',
    'repository',
    'last_activity_at',
    'size_bytes',
    'github',
  ];
  protected readonly agentFilter = signal('all');
  protected readonly statusFilter = signal('all');
  protected readonly pageIndex = signal(0);
  protected readonly pageSize = signal(25);
  protected readonly selectedSession = signal<AgentSession | null>(null);
  protected readonly health = httpResource<HealthResponse>(() => '/api/health');
  protected readonly inventory = httpResource<InventoryResponse>(() => '/api/sessions');
  protected readonly blocked = httpResource<BlockedResponse>(() => '/api/blocked');
  protected readonly github = httpResource<GitHubResponse>(() => {
    const session = this.selectedSession();
    return session ? `/api/sessions/${encodeURIComponent(session.id)}/github` : undefined;
  });

  protected readonly sessions = computed(() => this.inventory.value()?.sessions ?? []);
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
    () => this.health.isLoading() || this.inventory.isLoading() || this.blocked.isLoading(),
  );
  protected readonly failed = computed(
    () => !!(this.health.error() || this.inventory.error() || this.blocked.error()),
  );

  protected refresh(): void {
    this.health.reload();
    this.inventory.reload();
    this.blocked.reload();
    if (this.selectedSession()) {
      this.github.reload();
    }
  }

  protected setAgent(value: string): void {
    this.agentFilter.set(value);
    this.pageIndex.set(0);
  }

  protected setStatus(value: string): void {
    this.statusFilter.set(value);
    this.pageIndex.set(0);
  }

  protected setPage(event: PageEvent): void {
    this.pageIndex.set(event.pageIndex);
    this.pageSize.set(event.pageSize);
  }

  protected loadGitHub(session: AgentSession): void {
    this.selectedSession.set(session);
  }

  protected closeGitHub(): void {
    this.selectedSession.set(null);
  }

  protected agentName(agent: string): string {
    return agent === 'chatgpt' ? 'ChatGPT' : agent === 'codex' ? 'Codex' : agent;
  }

  protected statusName(status: string): string {
    return status === 'active' ? 'Activa' : status === 'archived' ? 'Archivada' : status;
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
}
