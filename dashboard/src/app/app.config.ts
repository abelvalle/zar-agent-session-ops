import { provideHttpClient } from '@angular/common/http';
import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { MatPaginatorIntl } from '@angular/material/paginator';

function spanishPaginator(): MatPaginatorIntl {
  const paginator = new MatPaginatorIntl();
  paginator.itemsPerPageLabel = 'Filas por página:';
  paginator.nextPageLabel = 'Página siguiente';
  paginator.previousPageLabel = 'Página anterior';
  paginator.firstPageLabel = 'Primera página';
  paginator.lastPageLabel = 'Última página';
  paginator.getRangeLabel = (page, pageSize, length) => {
    if (length === 0 || pageSize === 0) {
      return `0 de ${length}`;
    }
    const start = page * pageSize;
    const end = Math.min(start + pageSize, length);
    return `${start + 1} - ${end} de ${length}`;
  };
  return paginator;
}

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideHttpClient(),
    { provide: MatPaginatorIntl, useFactory: spanishPaginator },
  ],
};
