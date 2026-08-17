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

    http.expectOne('/api/health').flush({ status: 'ok', version: '0.30.0' });
    http.expectOne('/api/usage').flush(liveUsage());
    flushMaintenanceResources(http, 'ready');
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
    expect(page.textContent).toContain('API 0.30.0');
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
    expect(page.textContent).toContain('4%');
    expect(page.textContent).toContain('96% consumido');
    expect(page.textContent).toContain('hace menos de un minuto');
    expect(page.querySelector<HTMLAnchorElement>('a[download]')?.href).toContain(
      '/api/reports/weekly',
    );
    expect(page.textContent).toContain('Informe operativo con IA local');
    expect(page.textContent).toContain('Aún no hay informes operativos');
    [...page.querySelectorAll<HTMLButtonElement>('button')]
      .find((button) => button.textContent?.includes('Generar informe'))
      ?.click();
    const digestRequest = http.expectOne('/api/digests/weekly');
    expect(digestRequest.request.method).toBe('POST');
    expect(digestRequest.request.body).toEqual({ model: 'qwen3:8b' });
    const generatedDigest = {
      id: 1,
      generated_at: '2026-08-17T10:00:00Z',
      model: 'qwen3:8b',
      markdown: '# Weekly operational digest\n\n## Pending tasks\n\nAdd tests.',
    };
    digestRequest.flush(generatedDigest);
    await new Promise((resolve) => setTimeout(resolve));
    http.expectOne('/api/digests/weekly').flush({ count: 1, digests: [generatedDigest] });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(page.querySelector('.digest-content h1')?.textContent).toContain(
      'Weekly operational digest',
    );
    expect(page.textContent).toContain('Add tests.');
    expect(page.textContent).toContain('Políticas y mantenimiento');
    const policyInputs = page.querySelectorAll<HTMLInputElement>('.policy-fields input');
    policyInputs[0].value = '45';
    policyInputs[0].dispatchEvent(new Event('input'));
    policyInputs[1].value = '12';
    policyInputs[1].dispatchEvent(new Event('input'));
    fixture.detectChanges();
    [...page.querySelectorAll<HTMLButtonElement>('button')]
      .find((button) => button.textContent?.includes('Guardar política'))
      ?.click();
    const policyUpdate = http.expectOne('/api/policy');
    expect(policyUpdate.request.method).toBe('PUT');
    expect(policyUpdate.request.body).toEqual({
      archive_after_days: 45,
      blocked_after_hours: 12,
    });
    policyUpdate.flush({ archive_after_days: 45, blocked_after_hours: 12 });
    await new Promise((resolve) => setTimeout(resolve));
    http.expectOne('/api/policy').flush({ archive_after_days: 45, blocked_after_hours: 12 });
    http.expectOne('/api/blocked').flush({
      count: 1,
      threshold_hours: 12,
      sessions: [session('active-id', 'Build dashboard', 'active')],
    });
    http.expectOne('/api/retention').flush({
      count: 1,
      archive_after_days: 45,
      sessions: [session('active-id', 'Build dashboard', 'active')],
    });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(page.textContent).toContain('Política guardada');

    [...page.querySelectorAll<HTMLButtonElement>('button')]
      .find((button) => button.textContent?.includes('Ejecutar simulación'))
      ?.click();
    http.expectOne('/api/maintenance/preview').flush({
      id: 1,
      ran_at: '2026-08-11T20:00:00Z',
      mode: 'dry_run',
      archive_after_days: 45,
      blocked_after_hours: 12,
      archive_candidate_count: 1,
      blocked_candidate_count: 1,
    });
    await new Promise((resolve) => setTimeout(resolve));
    http.expectOne('/api/maintenance/history').flush({
      count: 1,
      runs: [
        {
          id: 1,
          ran_at: '2026-08-11T20:00:00Z',
          mode: 'dry_run',
          archive_after_days: 45,
          blocked_after_hours: 12,
          archive_candidate_count: 1,
          blocked_candidate_count: 1,
        },
      ],
    });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(page.textContent).toContain('No se movió ningún archivo');
    expect(page.textContent).toContain('Fuentes de sesiones');
    expect(page.textContent).toContain('Importar exportación ChatGPT');
    expect(page.textContent).toContain('OpenCode');
    expect(page.textContent).toContain('No configurada');
    const exportFile = new File(['[]'], 'chatgpt-export.json', {
      type: 'application/json',
    });
    Object.defineProperty(exportFile, 'arrayBuffer', {
      value: async () => new TextEncoder().encode('[]').buffer,
    });
    const exportInput = page.querySelector<HTMLInputElement>('.chatgpt-import input[type="file"]')!;
    Object.defineProperty(exportInput, 'files', { value: [exportFile] });
    exportInput.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    [...page.querySelectorAll<HTMLButtonElement>('button')]
      .find((button) => button.textContent?.includes('Analizar exportación'))
      ?.click();
    await new Promise((resolve) => setTimeout(resolve));
    const importPreview = http.expectOne('/api/imports/chatgpt/preview');
    expect(importPreview.request.headers.get('X-Filename')).toBe('chatgpt-export.json');
    importPreview.flush({
      conversation_count: 1,
      shown_count: 1,
      confirmation: 'IMPORT_CHATGPT',
      conversations: [
        {
          id: 'chatgpt-1',
          title: 'Imported conversation',
          last_activity_at: '2026-08-11T20:00:00Z',
          event_count: 4,
        },
      ],
    });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(page.textContent).toContain('1 conversaciones encontradas');
    [...page.querySelectorAll<HTMLButtonElement>('button')]
      .find((button) => button.textContent?.includes('Confirmar importación'))
      ?.click();
    await new Promise((resolve) => setTimeout(resolve));
    const importRequest = http.expectOne('/api/imports/chatgpt');
    expect(importRequest.request.headers.get('X-Confirmation')).toBe('IMPORT_CHATGPT');
    importRequest.flush({
      imported_count: 1,
      total_chatgpt_sessions: 1,
      stored_locally: true,
    });
    await new Promise((resolve) => setTimeout(resolve));
    http.expectOne('/api/sources').flush({
      sources: [
        {
          id: 'chatgpt',
          label: 'ChatGPT',
          status: 'imported',
          session_count: 1,
          import_supported: true,
        },
      ],
    });
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
      threshold_hours: 12,
      sessions: [session('active-id', 'Build dashboard', 'active')],
    });
    http.expectOne('/api/retention').flush({
      count: 1,
      archive_after_days: 45,
      sessions: [session('active-id', 'Build dashboard', 'active')],
    });
    http.expectOne('/api/archives').flush({ count: 0, archives: [] });
    http.expectOne('/api/reports/weekly').flush('# Weekly report');
    await fixture.whenStable();
    fixture.detectChanges();
    expect(page.textContent).toContain('1 conversaciones añadidas');

    const search = page.querySelector<HTMLInputElement>('input[type="search"]');
    expect(search).toBeTruthy();
    search!.value = 'CLAUDE-ID';
    search!.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    expect(inventory?.textContent).toContain('1 de 3 sesiones');
    expect(inventory?.textContent).toContain('Claude work');
    expect(inventory?.textContent).not.toContain('Old work');
    page.querySelector<HTMLButtonElement>('.clear-search')?.click();
    fixture.detectChanges();
    expect(search?.value).toBe('');
    expect(inventory?.textContent).toContain('3 sesiones visibles');

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
    http
      .expectOne('/api/sessions/codex-active-id-Build%20dashboard/activity')
      .flush(activityResponse());
    await fixture.whenStable();
    fixture.detectChanges();
    expect(page.textContent).toContain('Ficha operativa');
    expect(page.textContent).toContain('Consumo de tokens');
    expect(page.textContent).toContain('Total procesado1500');
    expect(page.textContent).toContain('Ship the widget');
    expect(page.textContent).toContain('Fusionada');
    expect(page.textContent).toContain('Relevo para continuar');
    expect(page.textContent).toContain('Actividad y siguiente paso');
    expect(page.textContent).toContain('Add regression tests');
    expect(page.textContent).toContain('Responder a la última petición pendiente');
    expect(page.textContent).toContain('Flujo de decisión');
    expect(page.textContent).toContain('1 · Revisar');
    expect(page.textContent).toContain('2 · Entender');
    expect(page.textContent).toContain('3 · Decidir');
    expect(page.textContent).toContain('Resumen local con Ollama');
    expect(page.textContent).toContain('qwen3:8b');

    [...page.querySelectorAll<HTMLButtonElement>('button')]
      .find((button) => button.textContent?.includes('Generar resumen'))
      ?.click();
    const summary = http.expectOne('/api/sessions/codex-active-id-Build dashboard/summary');
    expect(summary.request.method).toBe('POST');
    expect(summary.request.body).toEqual({ model: 'qwen3:8b' });
    summary.flush({
      model: 'qwen3:8b',
      markdown: '# Resumen local\n\nTrabajo revisado.',
      generated_at: '2026-08-11T20:00:00Z',
    });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(page.querySelector('.summary-content h1')?.textContent).toContain('Resumen local');

    [...page.querySelectorAll<HTMLButtonElement>('button')]
      .find((button) => button.textContent?.includes('Continuar con relevo'))
      ?.click();
    const handoff = http.expectOne('/api/sessions/codex-active-id-Build dashboard/handoff');
    expect(handoff.request.responseType).toBe('text');
    handoff.flush(
      '# Session handoff\n\n## Objective\n\nBuild dashboard\n\n<script>alert("unsafe")</script>',
    );
    await fixture.whenStable();
    fixture.detectChanges();

    expect(page.querySelector('.handoff-content h1')?.textContent).toContain('Session handoff');
    expect(page.querySelector('.handoff-content script')).toBeNull();
    expect(page.textContent).toContain('Copiar Markdown');
    expect(page.querySelector<HTMLAnchorElement>('.handoff-actions a')?.href).toContain(
      '/api/sessions/codex-active-id-Build%20dashboard/handoff',
    );
  });

  it('renders a retry state when the API is unavailable', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    for (const url of [
      '/api/health',
      '/api/usage',
      '/api/policy',
      '/api/maintenance/history',
      '/api/sources',
      '/api/ollama',
      '/api/digests/weekly',
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

    http.expectOne('/api/health').flush({ status: 'ok', version: '0.30.0' });
    http.expectOne('/api/usage').flush(liveUsage(true, 3600));
    flushMaintenanceResources(http);
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
    expect(page.textContent).toContain('Ollama está disponible, pero no hay modelos instalados');
    expect(page.textContent).toContain('Dato obsoleto');
    expect(page.textContent).toContain('hace 1 hora');
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

    http.expectOne('/api/health').flush({ status: 'ok', version: '0.30.0' });
    http.expectOne('/api/usage').flush(liveUsage());
    flushMaintenanceResources(http);
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

    const page = fixture.nativeElement as HTMLElement;
    const search = page.querySelector<HTMLInputElement>('input[type="search"]')!;
    search.value = 'Work 1';
    search.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    [...page.querySelectorAll<HTMLButtonElement>('.attention-panel button')]
      .find((button) => button.textContent?.includes('Revisar señal'))
      ?.click();
    fixture.detectChanges();
    await new Promise((resolve) => setTimeout(resolve));
    http.expectOne('/api/sessions/duplicate-id/github').flush({
      session_id: 'duplicate-id',
      count: 0,
      references: [],
    });
    http.expectOne('/api/sessions/codex-duplicate-id-Work%2025/activity').flush(activityResponse());
    fixture.detectChanges();

    expect(search.value).toBe('');
    expect(page.querySelector('mat-paginator')?.textContent).toContain('26 - 26 de 26');
    expect(page.querySelector('.session-title')?.textContent).toContain('Exact blocked record');
    expect(page.querySelector('.session-row--located')).toBeTruthy();
    expect(page.querySelector('.located-label')?.textContent).toContain('Localizada');
    expect(page.textContent).toContain('Fila localizada: Exact blocked record');
  });

  it('refreshes the inventory after the background scan completes', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    http.expectOne('/api/health').flush({ status: 'ok', version: '0.30.0' });
    http.expectOne('/api/usage').flush(liveUsage());
    flushMaintenanceResources(http);
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
    await new Promise((resolve) => setTimeout(resolve));
    http.expectOne('/api/usage').flush(liveUsage());
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
    http.expectOne('/api/health').flush({ status: 'ok', version: '0.30.0' });
    http.expectOne('/api/usage').flush(liveUsage());
    http.expectOne('/api/sources').flush({ sources: [] });
    http.expectOne('/api/ollama').flush({
      status: 'no_models',
      models: [],
      local_only: true,
    });
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

  it('dismisses and restores a false blocked signal from its detail', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const candidate = session('blocked-id', 'Reviewed session', 'active');

    http.expectOne('/api/health').flush({ status: 'ok', version: '0.30.0' });
    http.expectOne('/api/usage').flush(liveUsage());
    flushMaintenanceResources(http);
    http.expectOne('/api/sessions').flush({ count: 1, sessions: [candidate] });
    http.expectOne('/api/blocked').flush({
      count: 1,
      threshold_hours: 24,
      sessions: [candidate],
      dismissed_count: 0,
      dismissed: [],
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

    const page = fixture.nativeElement as HTMLElement;
    [...page.querySelectorAll<HTMLButtonElement>('button')]
      .find((button) => button.textContent?.includes('Revisar señal'))
      ?.click();
    fixture.detectChanges();
    http.expectOne('/api/sessions/blocked-id/github').flush({
      session_id: 'blocked-id',
      count: 0,
      references: [],
    });
    http
      .expectOne('/api/sessions/codex-blocked-id-Reviewed%20session/activity')
      .flush(activityResponse());
    expect(page.textContent).toContain('Revisión de bloqueo');

    [...page.querySelectorAll<HTMLButtonElement>('button')]
      .find((button) => button.textContent?.includes('Descartar falsa señal'))
      ?.click();
    fixture.detectChanges();
    expect(page.textContent).toContain('Su archivo no se modifica ni se mueve');

    [...page.querySelectorAll<HTMLButtonElement>('button')]
      .find((button) => button.textContent?.includes('Confirmar descarte'))
      ?.click();
    const dismissal = http.expectOne(`/api/sessions/${candidate.record_key}/blocked-dismissal`);
    expect(dismissal.request.body).toEqual({ confirmation: 'NOT_BLOCKED' });
    dismissal.flush({
      record_key: candidate.record_key,
      session_id: candidate.id,
      dismissed_at: '2026-08-09T10:00:00Z',
      reactivates_on_activity: true,
    });
    await new Promise((resolve) => setTimeout(resolve));
    http.expectOne('/api/sessions').flush({ count: 1, sessions: [candidate] });
    http.expectOne('/api/blocked').flush({
      count: 0,
      threshold_hours: 24,
      sessions: [],
      dismissed_count: 1,
      dismissed: [{ ...candidate, dismissed_at: '2026-08-09T10:00:00Z' }],
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
    expect(page.textContent).toContain('Señal descartada');
    expect(page.textContent).toContain('Señales descartadas');

    [...page.querySelectorAll<HTMLButtonElement>('button')]
      .find((button) => button.textContent?.includes('Deshacer descarte'))
      ?.click();
    http
      .expectOne(`/api/blocked-dismissals/${candidate.record_key}/restore`)
      .flush({ record_key: candidate.record_key, restored: true });
    await new Promise((resolve) => setTimeout(resolve));
    http.expectOne('/api/sessions').flush({ count: 1, sessions: [candidate] });
    http.expectOne('/api/blocked').flush({
      count: 1,
      threshold_hours: 24,
      sessions: [candidate],
      dismissed_count: 0,
      dismissed: [],
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
    expect(page.textContent).toContain('Marcar como no bloqueada');
  });

  it('previews, confirms and restores an archived session from its detail', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const candidate = session('old-id', 'Old session', 'active');

    http.expectOne('/api/health').flush({ status: 'ok', version: '0.30.0' });
    http.expectOne('/api/usage').flush(liveUsage());
    flushMaintenanceResources(http);
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
    http.expectOne('/api/sessions/codex-old-id-Old%20session/activity').flush(activityResponse());
    expect(page.textContent).toContain('Ciclo de vida');

    [...page.querySelectorAll<HTMLButtonElement>('button')]
      .find((button) => button.textContent?.includes('Revisar archivado'))
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
    http.expectOne('/api/sessions/codex-old-id-Old%20session/activity').flush(activityResponse());
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

function liveUsage(stale = false, ageSeconds = 45) {
  return {
    status: 'available',
    source: 'latest_local_codex_event',
    session_id: '019fcc83-61e6-7aa0-b008-7eb5bc44ca08',
    observed_at: '2026-08-10T14:17:52Z',
    age_seconds: ageSeconds,
    stale,
    usage: {
      observed_at: '2026-08-10T14:17:52Z',
      input_tokens: 2000,
      cached_input_tokens: 1500,
      output_tokens: 500,
      reasoning_output_tokens: 100,
      total_tokens: 2500,
      model_context_window: 258400,
      rate_limit_used_percent: 96,
      rate_limit_window_minutes: 10080,
      rate_limit_resets_at: '2026-08-15T22:59:43Z',
    },
  };
}

function activityResponse() {
  return {
    objective: 'Fix parser',
    latest_outcome: 'Parser fixed',
    pending_request: 'Add regression tests',
    next_action: 'respond_to_pending_request',
    recent_activity: [
      { role: 'assistant', text: 'Parser fixed' },
      { role: 'user', text: 'Add regression tests' },
    ],
    evidence: 'local_transcript_and_lifecycle_metadata',
  };
}

function flushMaintenanceResources(
  http: HttpTestingController,
  ollamaStatus: 'ready' | 'no_models' = 'no_models',
) {
  http.expectOne('/api/policy').flush({
    archive_after_days: 30,
    blocked_after_hours: 24,
  });
  http.expectOne('/api/maintenance/history').flush({ count: 0, runs: [] });
  http.expectOne('/api/sources').flush({
    sources: [
      {
        id: 'codex',
        label: 'Codex',
        status: 'available',
        session_count: 3,
        import_supported: false,
      },
      {
        id: 'claude',
        label: 'Claude Code',
        status: 'available',
        session_count: 1,
        import_supported: false,
      },
      {
        id: 'chatgpt',
        label: 'ChatGPT',
        status: 'awaiting_import',
        session_count: 0,
        import_supported: true,
      },
      {
        id: 'opencode',
        label: 'OpenCode',
        status: 'not_configured',
        session_count: 0,
        import_supported: false,
      },
    ],
  });
  http.expectOne('/api/ollama').flush({
    status: ollamaStatus,
    models: ollamaStatus === 'ready' ? ['qwen3:8b'] : [],
    local_only: true,
  });
  http.expectOne('/api/digests/weekly').flush({ count: 0, digests: [] });
}
