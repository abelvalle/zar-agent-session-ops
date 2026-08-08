import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { App } from './app';
import { appConfig } from './app.config';

describe('App', () => {
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [...appConfig.providers, provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('renders inventory and blocked-session data', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    http.expectOne('/api/health').flush({ status: 'ok', version: '0.20.0' });
    http.expectOne('/api/sessions').flush({
      count: 3,
      sessions: [
        session('active-id', 'Build dashboard', 'active'),
        session('archived-id', 'Old work', 'archived'),
        session('claude-id', 'Claude work', 'registered', 'claude'),
      ],
    });
    http.expectOne('/api/blocked').flush({
      count: 1,
      threshold_hours: 24,
      sessions: [session('active-id', 'Build dashboard', 'active')],
    });
    http.expectOne('/api/retention').flush({
      count: 1,
      archive_after_days: 30,
      sessions: [session('active-id', 'Build dashboard', 'active')],
    });
    http.expectOne('/api/archives').flush({ count: 0, archives: [] });
    http.expectOne('/api/reports/weekly').flush('# Weekly report');

    await fixture.whenStable();
    fixture.detectChanges();
    const page = fixture.nativeElement as HTMLElement;

    expect(page.querySelector('h1')?.textContent).toContain('Centro operativo de sesiones');
    expect(page.textContent).toContain('API 0.20.0');
    expect(page.textContent).toContain('Build dashboard');
    expect(page.textContent).toContain('Old work');
    expect(page.textContent).toContain('Claude Code');
    expect(page.textContent).toContain('Registrada');
    expect(page.textContent).toContain('Requieren revisión');
    expect(page.textContent).toContain('Qué requiere atención');
    expect(page.textContent).toContain('Candidatas a archivo');
    expect(page.textContent).toContain('Inicio detectado sin cierre');
    const attention = page.querySelector('.attention');
    const inventory = page.querySelector('.inventory');
    expect(attention?.compareDocumentPosition(inventory as Node)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
    expect(page.textContent).toContain('1 - 3 de 3');
    expect(page.querySelector('mat-paginator')).toBeTruthy();
    expect(page.textContent).toContain('Weekly report');
    expect(page.querySelector('.report-content h1')?.textContent).toContain('Weekly report');
    expect(page.textContent).toContain('Consumo de Codex');
    expect(page.textContent).toContain('84%');
    expect(page.querySelector<HTMLAnchorElement>('a[download]')?.href).toContain(
      '/api/reports/weekly',
    );

    page.querySelector<HTMLButtonElement>('.details-button')?.click();
    fixture.detectChanges();
    http.expectOne('/api/sessions/active-id/github').flush({
      session_id: 'active-id',
      count: 1,
      references: [
        {
          kind: 'pull',
          owner: 'acme',
          repository: 'widgets',
          identifier: '34',
          url: 'https://github.com/acme/widgets/pull/34',
          title: 'Ship the widget',
          state: 'merged',
        },
      ],
    });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(page.textContent).toContain('Ficha operativa');
    expect(page.textContent).toContain('Consumo de tokens');
    expect(page.textContent).toContain('Total procesado1500');
    expect(page.textContent).toContain('Ship the widget');
    expect(page.textContent).toContain('Fusionada');
  });

  it('renders a retry state when the API is unavailable', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    for (const url of [
      '/api/health',
      '/api/sessions',
      '/api/blocked',
      '/api/retention',
      '/api/archives',
    ]) {
      http.expectOne(url).flush('offline', { status: 503, statusText: 'Unavailable' });
    }
    http
      .expectOne('/api/reports/weekly')
      .flush('offline', { status: 503, statusText: 'Unavailable' });

    await fixture.whenStable();
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'No se pudo cargar el inventario',
    );
  });

  it('reads Markdown reports inline and recovers a failed report', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    http.expectOne('/api/health').flush({ status: 'ok', version: '0.20.0' });
    http.expectOne('/api/sessions').flush({ count: 0, sessions: [] });
    http.expectOne('/api/blocked').flush({ count: 0, threshold_hours: 24, sessions: [] });
    http.expectOne('/api/retention').flush({
      count: 0,
      archive_after_days: 30,
      sessions: [],
    });
    http.expectOne('/api/archives').flush({ count: 0, archives: [] });
    http
      .expectOne('/api/reports/weekly')
      .flush('offline', { status: 503, statusText: 'Unavailable' });
    await fixture.whenStable();
    fixture.detectChanges();

    const page = fixture.nativeElement as HTMLElement;
    expect(page.textContent).toContain('No se pudo cargar el informe');
    page.querySelector<HTMLButtonElement>('.report-retry')?.click();
    await new Promise((resolve) => setTimeout(resolve));
    http
      .expectOne('/api/reports/weekly')
      .flush('# Weekly report\n\n- Active sessions: 2\n\n<script>alert("unsafe")</script>');
    await fixture.whenStable();
    fixture.detectChanges();
    expect(page.querySelector('.report-content')?.textContent).toContain('Active sessions: 2');
    expect(page.querySelector('.report-content h1')?.textContent).toContain('Weekly report');
    expect(page.querySelector('.report-content script')).toBeNull();

    [...page.querySelectorAll<HTMLButtonElement>('.report-selector button')]
      .find((button) => button.textContent?.includes('Bloqueos'))
      ?.click();
    await new Promise((resolve) => setTimeout(resolve));
    http.expectOne('/api/reports/blocked').flush('# Potentially blocked\n\n- Candidates: 1');
    await fixture.whenStable();
    fixture.detectChanges();

    expect(page.querySelector('.report-content')?.textContent).toContain('Candidates: 1');
    const download = page.querySelector<HTMLAnchorElement>('a[download]');
    expect(download?.href).toContain('/api/reports/blocked');
    expect(download?.download).toBe('blocked.md');
  });

  it('locates the exact flagged record when a session id is duplicated', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    const sessions = Array.from({ length: 26 }, (_, index) =>
      session(
        index === 0 || index === 25 ? 'duplicate-id' : `session-${index}`,
        `Work ${index}`,
        'active',
      ),
    );
    sessions[25] = {
      ...sessions[25],
      title: 'Exact blocked record',
      last_activity_at: '2026-07-01T09:00:00Z',
      size_bytes: 4096,
    };

    http.expectOne('/api/health').flush({ status: 'ok', version: '0.20.0' });
    http.expectOne('/api/sessions').flush({ count: sessions.length, sessions });
    http.expectOne('/api/blocked').flush({
      count: 1,
      threshold_hours: 24,
      sessions: [sessions[25]],
    });
    http.expectOne('/api/retention').flush({
      count: 0,
      archive_after_days: 30,
      sessions: [],
    });
    http.expectOne('/api/archives').flush({ count: 0, archives: [] });
    http.expectOne('/api/reports/weekly').flush('# Weekly report');
    await fixture.whenStable();
    fixture.detectChanges();

    (fixture.nativeElement as HTMLElement)
      .querySelector<HTMLAnchorElement>('.attention-panel a')
      ?.click();
    await new Promise((resolve) => setTimeout(resolve));
    fixture.detectChanges();

    const page = fixture.nativeElement as HTMLElement;
    expect(page.querySelector('mat-paginator')?.textContent).toContain('26 - 26 de 26');
    expect(page.querySelector('.session-title')?.textContent).toContain(
      'Exact blocked record',
    );
    expect(page.querySelector('.session-row--located')).toBeTruthy();
    expect(page.querySelector('.located-label')?.textContent).toContain('Localizada');
    expect(page.textContent).toContain('Fila localizada: Exact blocked record');
  });

  it('refreshes the inventory after the background scan completes', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    http.expectOne('/api/health').flush({ status: 'ok', version: '0.20.0' });
    http.expectOne('/api/sessions').flush({ count: 0, sessions: [] });
    http.expectOne('/api/blocked').flush({ count: 0, threshold_hours: 24, sessions: [] });
    http.expectOne('/api/retention').flush({
      count: 0,
      archive_after_days: 30,
      sessions: [],
    });
    http.expectOne('/api/archives').flush({ count: 0, archives: [] });
    http.expectOne('/api/reports/weekly').flush('# Weekly report');
    await fixture.whenStable();
    fixture.detectChanges();

    const page = fixture.nativeElement as HTMLElement;
    [...page.querySelectorAll<HTMLButtonElement>('button')]
      .find((button) => button.textContent?.includes('Actualizar'))
      ?.click();
    http.expectOne('/api/refresh').flush({
      status: 'running',
      count: null,
      updated: null,
      reused: null,
      duration_seconds: null,
      started_at: '2026-08-04T10:00:00Z',
      finished_at: null,
      error: null,
    });
    await new Promise((resolve) => setTimeout(resolve));
    http.expectOne('/api/refresh').flush({
      status: 'completed',
      count: 1,
      updated: 1,
      reused: 0,
      duration_seconds: 1,
      started_at: '2026-08-04T10:00:00Z',
      finished_at: '2026-08-04T10:00:01Z',
      error: null,
    });
    await new Promise((resolve) => setTimeout(resolve));
    http.expectOne('/api/health').flush({ status: 'ok', version: '0.20.0' });
    http.expectOne('/api/sessions').flush({
      count: 1,
      sessions: [session('refreshed-id', 'Fresh work', 'active')],
    });
    http.expectOne('/api/blocked').flush({
      count: 0,
      threshold_hours: 24,
      sessions: [],
    });
    http.expectOne('/api/retention').flush({
      count: 0,
      archive_after_days: 30,
      sessions: [],
    });
    http.expectOne('/api/archives').flush({ count: 0, archives: [] });
    http.expectOne('/api/reports/weekly').flush('# Weekly report updated');
    await fixture.whenStable();
    fixture.detectChanges();

    expect(page.textContent).toContain('Actualizado en 1.0 s: 1 con cambios y 0 sin cambios');
    expect(page.textContent).toContain('Fresh work');
  });

  it('previews, confirms and restores an archived session from its detail', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const candidate = session('old-id', 'Old session', 'active');

    http.expectOne('/api/health').flush({ status: 'ok', version: '0.20.0' });
    http.expectOne('/api/sessions').flush({ count: 1, sessions: [candidate] });
    http.expectOne('/api/blocked').flush({ count: 0, threshold_hours: 24, sessions: [] });
    http.expectOne('/api/retention').flush({
      count: 1,
      archive_after_days: 30,
      sessions: [candidate],
    });
    http.expectOne('/api/archives').flush({ count: 0, archives: [] });
    http.expectOne('/api/reports/weekly').flush('# Weekly report');
    await fixture.whenStable();
    fixture.detectChanges();

    const page = fixture.nativeElement as HTMLElement;
    [...page.querySelectorAll<HTMLButtonElement>('button')]
      .find((button) => button.textContent?.includes('Revisar y archivar'))
      ?.click();
    fixture.detectChanges();
    http.expectOne('/api/sessions/old-id/github').flush({
      session_id: 'old-id',
      count: 0,
      references: [],
    });
    expect(page.textContent).toContain('Ciclo de vida');

    [...page.querySelectorAll<HTMLButtonElement>('button')]
      .find((button) => button.textContent?.includes('Preparar archivado'))
      ?.click();
    http.expectOne(`/api/sessions/${candidate.record_key}/archive`).flush({
      record_key: candidate.record_key,
      session_id: candidate.id,
      title: candidate.title,
      source_name: 'old.jsonl',
      destination_name: 'old.jsonl',
      size_bytes: candidate.size_bytes,
      archive_after_days: 30,
      confirmation: 'ARCHIVE',
    });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(page.textContent).toContain('Confirmar moverá el archivo');
    expect(page.textContent).toContain('old.jsonl');

    [...page.querySelectorAll<HTMLButtonElement>('button')]
      .find((button) => button.textContent?.includes('Confirmar archivado'))
      ?.click();
    const archive = http.expectOne(`/api/sessions/${candidate.record_key}/archive`);
    expect(archive.request.body).toEqual({ confirmation: 'ARCHIVE' });
    archive.flush({
      record_key: candidate.record_key,
      session_id: candidate.id,
      title: candidate.title,
      destination_name: 'old.jsonl',
      recovery_available: true,
    });
    await new Promise((resolve) => setTimeout(resolve));
    http.expectOne('/api/sessions').flush({ count: 0, sessions: [] });
    http.expectOne('/api/blocked').flush({ count: 0, threshold_hours: 24, sessions: [] });
    http.expectOne('/api/retention').flush({
      count: 0,
      archive_after_days: 30,
      sessions: [],
    });
    http.expectOne('/api/archives').flush({
      count: 1,
      archives: [
        {
          record_key: candidate.record_key,
          session_id: candidate.id,
          title: candidate.title,
          agent: candidate.agent,
          size_bytes: candidate.size_bytes,
          archived_at: '2026-08-08T10:00:00Z',
          destination_name: 'old.jsonl',
        },
      ],
    });
    http.expectOne('/api/reports/weekly').flush('# Weekly report');
    await fixture.whenStable();
    fixture.detectChanges();
    expect(page.textContent).toContain('Sesión archivada');
    expect(page.textContent).toContain('Deshacer archivado');
    expect(page.textContent).toContain('Archivadas recuperables');

    [...page.querySelectorAll<HTMLButtonElement>('button')]
      .find((button) => button.textContent?.trim() === 'Cerrar')
      ?.click();
    fixture.detectChanges();
    [...page.querySelectorAll<HTMLButtonElement>('button')]
      .find((button) => button.textContent?.trim() === 'Restaurar')
      ?.click();
    http.expectOne(`/api/archives/${candidate.record_key}/restore`).flush({
      record_key: candidate.record_key,
      session_id: candidate.id,
      restored: true,
      session: candidate,
    });
    await new Promise((resolve) => setTimeout(resolve));
    http.expectOne('/api/sessions/old-id/github').flush({
      session_id: 'old-id',
      count: 0,
      references: [],
    });
    http.expectOne('/api/sessions').flush({ count: 1, sessions: [candidate] });
    http.expectOne('/api/blocked').flush({ count: 0, threshold_hours: 24, sessions: [] });
    http.expectOne('/api/retention').flush({
      count: 1,
      archive_after_days: 30,
      sessions: [candidate],
    });
    http.expectOne('/api/archives').flush({ count: 0, archives: [] });
    http.expectOne('/api/reports/weekly').flush('# Weekly report');
    await fixture.whenStable();
    fixture.detectChanges();
    expect(page.textContent).toContain('Preparar archivado');
  });
});

function session(id: string, title: string, status: string, agent = 'codex') {
  return {
    record_key: `${agent}-${id}-${title}`,
    id,
    agent,
    title,
    status,
    repository: 'D:/repo',
    started_at: '2026-08-04T08:00:00Z',
    last_activity_at: '2026-08-04T09:00:00Z',
    size_bytes: 2048,
    event_count: 4,
    origin: 'Codex Desktop',
    thread_source: 'user',
    last_event_type: 'task_started',
    usage:
      agent === 'codex'
        ? {
            observed_at: '2026-08-04T09:00:00Z',
            input_tokens: 1200,
            cached_input_tokens: 900,
            output_tokens: 300,
            reasoning_output_tokens: 100,
            total_tokens: 1500,
            model_context_window: 258400,
            rate_limit_used_percent: 16,
            rate_limit_window_minutes: 10080,
            rate_limit_resets_at: '2026-08-11T09:00:00Z',
          }
        : null,
  };
}
