import { Link } from 'react-router-dom';

export default function NotFoundPage() {
  return (
    <main className="page-narrow">
      <h1>Page not found</h1>
      <p>The page you asked for does not exist or you do not have access to it.</p>
      <Link to="/">Go to the start page</Link>
    </main>
  );
}
