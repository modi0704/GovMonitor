export default function FormError({ message }: { message: string | null | undefined }) {
  if (!message) return null;
  return (
    <p className="form-error" role="alert">
      {message}
    </p>
  );
}
