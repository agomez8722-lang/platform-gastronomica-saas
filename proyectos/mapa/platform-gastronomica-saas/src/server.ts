import 'dotenv/config';
import { app } from './app';
import chatRouter from './routes/chat';

app.use('/api/chat', chatRouter);

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => console.log(`Gastronomica SaaS en http://localhost:${PORT}`));
