import { useMemo, useState } from 'react';
import GuideContent from './GuideContent';
import content from './userGuide.generated.json';
import './user-guide.css';

export default function UserGuidePage() {
  const [query, setQuery] = useState('');
  const [chosen, setChosen] = useState(content.sections[0]!.id);
  const sections = useMemo(() => {
    const search = query.trim().toLowerCase();
    return content.sections.filter((section) =>
      `${section.title} ${section.markdown}`.toLowerCase().includes(search),
    );
  }, [query]);
  const index = content.sections.findIndex((section) => section.id === chosen);
  const section = content.sections[index]!;
  return (
    <section className="page user-guide-page">
      <div className="page-heading guide-actions">
        <div>
          <h1>User guide</h1>
          <p className="muted">Find a screen, follow a task, or learn what your results mean.</p>
        </div>
        <div className="row">
          <a className="btn btn-primary" href="/user-guide/USER_GUIDE.pdf" download>
            Download PDF
          </a>
          <a className="btn" href="/user-guide/USER_GUIDE_WITH_SAMPLE_DATA.pdf" download>
            Practice guide with sample data (PDF)
          </a>
          <button type="button" className="btn" onClick={() => window.print()}>
            Print section
          </button>
        </div>
      </div>
      <div className="guide-layout">
        <aside className="card guide-index guide-actions" aria-label="Guide contents">
          <label htmlFor="guide-search">Find a topic</label>
          <input
            id="guide-search"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <p className="muted small" role="status">
            {sections.length} {sections.length === 1 ? 'section' : 'sections'} found
          </p>
          <nav aria-label="User guide sections">
            {sections.map((item) => (
              <button
                key={item.id}
                type="button"
                aria-current={item.id === chosen ? 'page' : undefined}
                onClick={() => setChosen(item.id)}
              >
                {item.title}
              </button>
            ))}
          </nav>
          {sections.length === 0 && (
            <p>No matching topic. Try a screen name such as Plans or Dashboard.</p>
          )}
        </aside>
        <article className="card guide-article" aria-labelledby="guide-section-title">
          <p className="muted small">
            Section {index + 1} of {content.sections.length}
          </p>
          <h2 id="guide-section-title">{section.title}</h2>
          <GuideContent markdown={section.markdown} />
          <div className="guide-paging guide-actions">
            <button
              type="button"
              className="btn"
              disabled={index === 0}
              onClick={() => setChosen(content.sections[index - 1]!.id)}
            >
              Previous section
            </button>
            <button
              type="button"
              className="btn"
              disabled={index === content.sections.length - 1}
              onClick={() => setChosen(content.sections[index + 1]!.id)}
            >
              Next section
            </button>
          </div>
        </article>
      </div>
    </section>
  );
}
