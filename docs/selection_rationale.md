# Selection Rationale

## Problem Overview
Cryptocurrency markets are highly volatile and can experience sudden spikes in price movements. Detecting volatility spikes in real time is important for risk management, trading strategies, and monitoring market stability.

## Why This Problem
We selected this problem because it combines real time data processing with machine learning based prediction, which aligns well with the objectives of building operational AI systems. It also reflects real world use cases in financial analytics and trading systems.

## Approach
Our system uses a machine learning model (Logistic Regression pipeline) trained on engineered features such as log returns, spread, volatility, and trade intensity. The model predicts the probability of a volatility spike.

For the interim submission, we implemented:
- A FastAPI based prediction service
- Model loading and inference pipeline
- Replay mode using sample data
- Core endpoints for health, prediction, versioning, and metrics

## Why This Architecture
We chose a modular architecture to separate concerns:
- FastAPI for serving predictions
- Docker for containerization
- Replay data for simulating streaming input
- Prometheus metrics for monitoring

This design ensures scalability and ease of integration with real time streaming systems like Kafka in future iterations.

## Trade-offs
- We used a simple Logistic Regression model for faster deployment and easier debugging instead of a more complex model.
- Replay mode is used instead of real time streaming to simplify the initial implementation.
- Monitoring is basic and will be extended in future versions.

## Future Improvements
- Integrate Kafka for real time streaming data
- Use more advanced models such as deep learning or ensemble methods
- Add MLflow for experiment tracking and model versioning
- Enhance monitoring with dashboards and alerting systems
- Improve model accuracy with more features and tuning

## Conclusion
This system demonstrates a functional end to end pipeline for deploying a machine learning model as a real time service. The interim version establishes a strong foundation that can be extended into a production grade system.