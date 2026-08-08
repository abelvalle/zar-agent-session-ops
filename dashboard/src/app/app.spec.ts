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

    http.expectOne('/api/health').flush({ status: 'ok', version: '0.17.0' });
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

    await fixture.whenStable();
    fixture.detectChanges();
    const page = fixture.nativeElement as HTMLElement;

    expect(page.querySelector('h1')?.textContent).toContain('Centro operativo de sesiones');
    expect(page.textContent).toContain('API 0.17.0');
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
    for (const report of ['sessions', 'weekly', 'blocked']) {
      const link = page.querySelector<HTMLAnchorElement>(`a[href="/api/reports/${report}"]`);
      expect(link).toBeTruthy();
      expect(link?.hasAttribute('download')).toBe(true);
    }

    page.querySelector<HTMLButtonElement>('.github-button')?.click();
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
    expect(page.textContent).toContain('Ship the widget');
    expect(page.textContent).toContain('Fusionada');
  });

  it('renders a retry state when the API is unavailable', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    for (const url of ['/api/health', '/api/sessions', '/api/blocked', '/api/retention']) {
      http.expectOne(url).flush('offline', { status: 503, statusText: 'Unavailable' });
    }

    await fixture.whenStable();
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'No se pudo cargar el inventario',
    );
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

    http.expectOne('/api/health').flush({ status: 'ok', version: '0.17.0' });
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
    await fixture.whenStable();
    fixture.detectChanges();

    (fixture.nativeElement as HTMLElement)
      .querySelector<HTMLAnchorElement>('.attention-panel a')
      ?.click();
    fixture.detectChanges();

    const page = fixture.nativeElement as HTMLElement;
    expect(page.querySelector('mat-paginator')?.textContent).toContain('26 - 26 de 26');
    expect(page.querySelector('.session-title')?.textContent).toContain(
      'Exact blocked record',
    );
  });

  it('refreshes the inventory after the background scan completes', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();

    http.expectOne('/api/health').flush({ status: 'ok', version: '0.17.0' });
    http.expectOne('/api/sessions').flush({ count: 0, sessions: [] });
    http.expectOne('/api/blocked').flush({ count: 0, threshold_hours: 24, sessions: [] });
    http.expectOne('/api/retention').flush({
      count: 0,
      archive_after_days: 30,
      sessions: [],
    });
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
    http.expectOne('/api/health').flush({ status: 'ok', version: '0.17.0' });
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
    await fixture.whenStable();
    fixture.detectChanges();

    expect(page.textContent).toContain('Actualizado en 1.0 s: 1 con cambios y 0 sin cambios');
    expect(page.textContent).toContain('Fresh work');
  });
});

function session(id: string, title: string, status: string, agent = 'codex') {
  return {
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
  };
}
