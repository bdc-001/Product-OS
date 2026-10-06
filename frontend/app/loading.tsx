import Box from "@mui/material/Box";
import Skeleton from "@mui/material/Skeleton";

export default function Loading() {
  return <Box role="status" aria-label="Loading page" sx={{ p: { xs: 2, md: 4 } }}>
    <Skeleton width="35%" height={56} />
    <Skeleton width="60%" height={24} />
    <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "repeat(2, 1fr)" }, gap: 3, mt: 4 }}>
      {[1, 2, 3, 4].map((id) => <Skeleton key={id} variant="rounded" height={180} sx={{ borderRadius: "18px" }} />)}
    </Box>
  </Box>;
}
